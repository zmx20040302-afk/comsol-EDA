"""Build a generated MATLAB model in COMSOL, optionally running its approved study."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comsol_small_model.comsol_server import ensure_comsol_server  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path, help="Generated MATLAB builder to validate.")
    parser.add_argument("--timeout", type=int, default=120, help="MATLAB timeout in seconds.")
    parser.add_argument("--solve", action="store_true", help="Run the generated study after building the model.")
    parser.add_argument(
        "--export-joule-results",
        action="store_true",
        help="Export Vtot, Tmax, and Tavg after solving the verified rectangle Joule-heating benchmark.",
    )
    parser.add_argument("--results-csv", type=Path, help="Destination CSV for exported Joule-heating results.")
    parser.add_argument(
        "--sweep-range-mv",
        type=float,
        nargs=3,
        metavar=("START", "STEP", "STOP"),
        help="Override the Joule benchmark sweep with start, step, and stop values in mV.",
    )
    args = parser.parse_args()

    config = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    host = str(config.get("comsol_server_host", "localhost"))
    port = int(config.get("comsol_server_port", 2036))
    script = args.script.resolve() if args.script else _latest_builder()
    function_name = _function_name(script)
    model_path = script.with_name(f"{function_name}_buildcheck.mph")
    results_csv = (
        args.results_csv.resolve()
        if args.results_csv is not None
        else script.with_name(f"{function_name}_results.csv")
        if args.export_joule_results
        else None
    )
    sweep_range_mv = tuple(args.sweep_range_mv) if args.sweep_range_mv is not None else (0.1, 0.025, 1.0)
    previous_model_mtime = model_path.stat().st_mtime_ns if model_path.is_file() else None
    report = {
        "kind": "comsol_build_check",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "script": str(script),
        "model_path": str(model_path),
        "host": host,
        "port": port,
        "study_executed": args.solve,
    }
    if args.export_joule_results and not args.solve:
        report.update({"ok": False, "error": "--export-joule-results requires --solve."})
        _write_report(report)
        print(json.dumps(report, ensure_ascii=False))
        return 1
    if args.sweep_range_mv is not None and (not args.solve or not args.export_joule_results):
        report.update({"ok": False, "error": "--sweep-range-mv requires --solve and --export-joule-results."})
        _write_report(report)
        print(json.dumps(report, ensure_ascii=False))
        return 1
    if sweep_range_mv[0] <= 0 or sweep_range_mv[1] <= 0 or sweep_range_mv[2] < sweep_range_mv[0]:
        report.update({"ok": False, "error": "Invalid millivolt sweep range."})
        _write_report(report)
        print(json.dumps(report, ensure_ascii=False))
        return 1
    if results_csv is not None:
        report["results_csv"] = str(results_csv)
        report["sweep_range_mv"] = list(sweep_range_mv)

    server = _ensure_comsol_server(config, host, port)
    report["server"] = server
    if not server["ready"]:
        report.update({"ok": False, "error": str(server["message"])})
        _write_report(report)
        print(json.dumps(report, ensure_ascii=False))
        return 1

    matlab = Path(str(config.get("matlab_executable", "")))
    mli = Path(str(config.get("livelink_matlab_path", "")))
    if not matlab.is_file() or not mli.is_dir():
        report.update({"ok": False, "error": "MATLAB executable or LiveLink path is unavailable."})
        _write_report(report)
        print(json.dumps(report, ensure_ascii=False))
        return 1

    batch = _matlab_batch(script, function_name, model_path, mli, host, port, args.solve, results_csv, sweep_range_mv)
    completed = subprocess.run(
        [str(matlab), "-batch", batch],
        cwd=script.parent,
        text=True,
        capture_output=True,
        timeout=args.timeout,
        check=False,
    )
    report.update(
        {
            "ok": completed.returncode == 0
            and _was_model_updated(model_path, previous_model_mtime)
            and (results_csv is None or _csv_has_data(results_csv)),
            "matlab_exit_code": completed.returncode,
            "model_exists": model_path.is_file(),
            "model_updated_this_run": _was_model_updated(model_path, previous_model_mtime),
            "results_csv_exists": results_csv.is_file() if results_csv is not None else False,
            "results_csv_has_rows": _csv_has_data(results_csv) if results_csv is not None else False,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
    )
    report_path = _report_path()
    report["report"] = str(report_path)
    _write_report(report, report_path)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


def _latest_builder() -> Path:
    builders = sorted(
        (ROOT / "generated" / "staged_workflows" / "final_code").glob("*.m"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not builders:
        raise FileNotFoundError("No generated MATLAB builder was found.")
    return builders[0]


def _function_name(script: Path) -> str:
    first_line = script.read_text(encoding="utf-8").splitlines()[0]
    match = re.match(r"function\s+model\s*=\s*([A-Za-z][A-Za-z0-9_]*)\(\)", first_line)
    if not match:
        raise ValueError(f"Cannot determine MATLAB function name from {script}")
    return match.group(1)


def _matlab_batch(
    script: Path,
    function_name: str,
    model_path: Path,
    mli: Path,
    host: str,
    port: int,
    solve: bool,
    results_csv: Path | None,
    sweep_range_mv: tuple[float, float, float],
) -> str:
    def quote(path: Path) -> str:
        return path.as_posix().replace("'", "''")

    start_mv, step_mv, stop_mv = sweep_range_mv
    sweep_expression = f"range({start_mv:g}[mV],{step_mv:g}[mV],{stop_mv:g}[mV])"
    solve_command = (
        f"model.study('std1').feature('param').set('plistarr', {{'{sweep_expression}'}}); "
        "model.study('std1').run; disp('STUDY_SOLVE_OK'); "
        if solve
        else ""
    )
    export_command = ""
    if results_csv is not None:
        output = quote(results_csv)
        export_command = (
            "tmax=mphglobal(model,'maxop1(T)'); "
            "tavg=mphglobal(model,'aveop1(T)'); "
            "tmax=tmax(:); tavg=tavg(:); n=min(numel(tmax),numel(tavg)); "
            "if n < 1, error('No Joule-temperature results were returned by COMSOL.'); end; "
            f"Vtot_V=({start_mv:g}:{step_mv:g}:({start_mv:g}+{step_mv:g}*(n-1)))'*1e-3; "
            "result_table=table(Vtot_V,tmax(1:n),tavg(1:n),'VariableNames',{'Vtot_V','Tmax_K','Tavg_K'}); "
            f"writetable(result_table,'{output}'); "
            f"disp('JOULE_RESULTS_CSV={output}'); "
        )
    return (
        f"addpath('{quote(mli)}'); mphstart('{host}',{port}); "
        f"addpath('{quote(script.parent)}'); model={function_name}(); "
        f"{solve_command}{export_command}mphsave(model,'{quote(model_path)}'); disp('BUILD_CHECK_OK');"
    )


def _can_connect(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def _ensure_comsol_server(config: dict[str, object], host: str, port: int) -> dict[str, object]:
    log_path = ROOT / "generated" / "training_runs" / f"comsol_mphserver_{datetime.now().strftime('%Y%m%d%H%M%S')}.log"
    result = ensure_comsol_server(config, log_path=log_path, detached=True)
    result["started_by_check"] = bool(result.pop("started", False))
    return result


def _was_model_updated(model_path: Path, previous_mtime: int | None) -> bool:
    if not model_path.is_file():
        return False
    return previous_mtime is None or model_path.stat().st_mtime_ns != previous_mtime


def _csv_has_data(path: Path) -> bool:
    if not path.is_file():
        return False
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        return False
    try:
        return all(
            math.isfinite(float(row["Vtot_V"]))
            and math.isfinite(float(row["Tmax_K"]))
            and math.isfinite(float(row["Tavg_K"]))
            for row in rows
        )
    except (KeyError, TypeError, ValueError):
        return False


def _report_path() -> Path:
    destination = ROOT / "generated" / "training_runs" / f"comsol_build_check_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    destination.mkdir(parents=True, exist_ok=True)
    return destination / "comsol_build_check.json"


def _write_report(report: dict[str, object], path: Path | None = None) -> Path:
    path = path or _report_path()
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
