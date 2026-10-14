from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from benchmark_comsol_repeated import (
    WindowsProcessTreeMonitor,
    _find_process_pids,
    _percentile,
    _quote_matlab,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "generated" / "benchmarks" / "busbar_joule_heat" / "builders"
SOURCE_MODEL = SOURCE_DIR / "busbar_joule_heat_baseline.mph"
DEFAULT_OUTPUTS = {
    "verification9": ROOT / "generated" / "benchmarks" / "busbar_multiphysics_sweep_20261009",
    "dense49": ROOT / "generated" / "benchmarks" / "busbar_dense_multiphysics_sweep_20261009",
}


def _matlab_runner(
    *,
    output_dir: Path,
    mli: Path,
    host: str,
    port: int,
    voltages_mv: tuple[float, ...],
    heat_transfer_coefficients: tuple[float, ...],
) -> str:
    source_model = _quote_matlab(SOURCE_MODEL)
    output_csv = _quote_matlab(output_dir / "busbar_multiphysics_sweep.csv")
    output_model = _quote_matlab(output_dir / "busbar_multiphysics_sweep_final.mph")
    error_path = _quote_matlab(output_dir / "busbar_multiphysics_sweep.error.txt")
    voltage_expression = " ".join(f"{value:.12g}" for value in voltages_mv)
    htc_expression = " ".join(f"{value:.12g}" for value in heat_transfer_coefficients)
    expected_cases = len(voltages_mv) * len(heat_transfer_coefficients)
    return f"""addpath('{_quote_matlab(mli)}');
mphstart('{host.replace("'", "''")}', {port});
model = mphopen('{source_model}');
voltages_mv = [{voltage_expression}];
heat_transfer_coefficients = [{htc_expression}];
output_path = '{output_csv}';
error_path = '{error_path}';
if isfile(error_path), delete(error_path); end
result = table();
potential_selection = mphgetselection(model.component('comp1').physics('ec').feature('pot1'));
convection_selection = mphgetselection(model.component('comp1').physics('ht').feature('hf1'));
total_timer = tic;
try
  for voltage_mv = voltages_mv
    for htc_w_m2k = heat_transfer_coefficients
      model.param.set('Vtot', sprintf('%g[mV]', voltage_mv));
      model.param.set('htc', sprintf('%g[W/(m^2*K)]', htc_w_m2k));
      case_timer = tic;
      model.study('std1').run;
      solve_seconds = toc(case_timer);
      tmax_k = mphmax(model, 'T', 3);
      terminal_current_a = abs(mphint2(model, 'ec.nJ', 2, 'selection', potential_selection.entities'));
      joule_power_w = mphint2(model, 'ec.Qh', 3);
      convection_power_w = abs(mphint2(model, 'ht.nteflux', 2, 'selection', convection_selection.entities'));
      energy_imbalance_percent = abs(joule_power_w-convection_power_w)/joule_power_w*100;
      next_row = table(voltage_mv, htc_w_m2k, tmax_k, tmax_k-273.15, terminal_current_a, joule_power_w, convection_power_w, energy_imbalance_percent, solve_seconds, ...
        'VariableNames', {{'Vtot_mV', 'htc_W_m2K', 'Tmax_K', 'Tmax_C', 'terminal_current_A', 'joule_power_W', 'convection_power_W', 'energy_imbalance_percent', 'solve_seconds'}});
      result = [result; next_row]; %#ok<AGROW>
      writetable(result, output_path);
      fprintf('BUSBAR_SWEEP_CASE %d/{expected_cases} Vtot=%g htc=%g solve_seconds=%.6f\\n', height(result), voltage_mv, htc_w_m2k, solve_seconds);
    end
  end
  mphsave(model, '{output_model}');
  fprintf('BUSBAR_SWEEP_SUCCESS cases=%d measured_total_seconds=%.6f\\n', height(result), toc(total_timer));
catch errorInfo
  error_file = fopen(error_path, 'w');
  fprintf(error_file, '%s\\n', getReport(errorInfo, 'extended', 'hyperlinks', 'off'));
  fclose(error_file);
  rethrow(errorInfo);
end
"""


def _read_rows(path: Path) -> list[dict[str, float]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: float(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def _physics_checks(
    rows: list[dict[str, float]],
    *,
    voltages_mv: tuple[float, ...],
    heat_transfer_coefficients: tuple[float, ...],
) -> dict[str, object]:
    expected = {(round(float(v), 8), round(float(h), 8)) for v in voltages_mv for h in heat_transfer_coefficients}
    observed = {(round(row["Vtot_mV"], 8), round(row["htc_W_m2K"], 8)) for row in rows}
    finite = all(
        value == value and abs(value) != float("inf")
        for row in rows
        for value in row.values()
    )
    voltage_monotonic = True
    for htc in heat_transfer_coefficients:
        group = sorted((row for row in rows if abs(row["htc_W_m2K"] - htc) < 1e-9), key=lambda row: row["Vtot_mV"])
        for name in ("Tmax_K", "terminal_current_A", "joule_power_W"):
            values = [row[name] for row in group]
            voltage_monotonic &= all(right > left for left, right in zip(values, values[1:]))
    convection_monotonic = True
    for voltage in voltages_mv:
        group = sorted((row for row in rows if abs(row["Vtot_mV"] - voltage) < 1e-9), key=lambda row: row["htc_W_m2K"])
        values = [row["Tmax_K"] for row in group]
        convection_monotonic &= all(right < left for left, right in zip(values, values[1:]))
    max_imbalance = max(row["energy_imbalance_percent"] for row in rows) if rows else None
    checks = {
        "row_count_matches_expected": len(rows) == len(expected),
        "input_grid_complete": observed == expected,
        "all_values_finite": finite,
        "temperature_current_and_power_increase_with_voltage": voltage_monotonic,
        "temperature_decreases_with_convection": convection_monotonic,
        "energy_imbalance_below_0_1_percent": max_imbalance is not None and max_imbalance < 0.1,
    }
    return {
        "checks": checks,
        "all_passed": all(checks.values()),
        "maximum_energy_imbalance_percent": max_imbalance,
        "minimum_Tmax_C": min(row["Tmax_C"] for row in rows) if rows else None,
        "maximum_Tmax_C": max(row["Tmax_C"] for row in rows) if rows else None,
    }


def _historical_dense_comparison(rows: list[dict[str, float]]) -> dict[str, object] | None:
    historical_path = SOURCE_DIR / "busbar_dense_training_data.csv"
    if not historical_path.is_file():
        return None
    historical = _read_rows(historical_path)
    keys = lambda row: (round(row["Vtot_mV"], 8), round(row["htc_W_m2K"], 8))
    new_by_key = {keys(row): row for row in rows}
    old_by_key = {keys(row): row for row in historical}
    shared = sorted(set(new_by_key) & set(old_by_key))
    output_names = (
        "Tmax_K",
        "Tmax_C",
        "terminal_current_A",
        "joule_power_W",
        "convection_power_W",
        "energy_imbalance_percent",
    )
    maximum_absolute_differences = {
        name: max(abs(new_by_key[key][name] - old_by_key[key][name]) for key in shared)
        for name in output_names
    }
    checks = {
        "all_49_historical_rows_matched": len(rows) == len(historical) == len(shared) == 49,
        "maximum_temperature_difference_below_0_001_K": maximum_absolute_differences["Tmax_K"] < 0.001,
        "maximum_energy_imbalance_difference_below_1e_6_percent": (
            maximum_absolute_differences["energy_imbalance_percent"] < 1e-6
        ),
    }
    return {
        "source_csv": str(historical_path.relative_to(ROOT)),
        "matched_rows": len(shared),
        "maximum_absolute_differences": maximum_absolute_differences,
        "checks": checks,
        "all_passed": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the complete 3D busbar Joule-heating sweep")
    parser.add_argument("--grid", choices=sorted(DEFAULT_OUTPUTS), default="verification9")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=1200.0)
    args = parser.parse_args()
    config = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    matlab = Path(config["matlab_executable"])
    mli = Path(config["livelink_matlab_path"])
    if not matlab.is_file() or not mli.is_dir() or not SOURCE_MODEL.is_file():
        raise FileNotFoundError("MATLAB, LiveLink, or the source busbar MPH is missing")
    mphserver_pids = _find_process_pids({"comsolmphserver.exe"})
    if not mphserver_pids:
        raise RuntimeError("No running comsolmphserver.exe process was found")

    if args.grid == "dense49":
        voltages_mv = tuple(10.0 + index * (20.0 / 6.0) for index in range(7))
        heat_transfer_coefficients = tuple(2.0 + index * (8.0 / 6.0) for index in range(7))
    else:
        voltages_mv = (10.0, 20.0, 30.0)
        heat_transfer_coefficients = (2.0, 5.0, 10.0)
    output_dir = (args.output_dir or DEFAULT_OUTPUTS[args.grid]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "busbar_multiphysics_sweep.csv"
    model_path = output_dir / "busbar_multiphysics_sweep_final.mph"
    runner_path = output_dir / "run_busbar_multiphysics_sweep.m"
    log_path = output_dir / "busbar_multiphysics_sweep.log"
    error_path = output_dir / "busbar_multiphysics_sweep.error.txt"
    for path in (csv_path, model_path, log_path, error_path):
        path.unlink(missing_ok=True)
    runner_path.write_text(
        _matlab_runner(
            output_dir=output_dir,
            mli=mli,
            host=str(config.get("comsol_server_host", "localhost")),
            port=int(config.get("comsol_server_port", 2036)),
            voltages_mv=voltages_mv,
            heat_transfer_coefficients=heat_transfer_coefficients,
        ),
        encoding="utf-8",
    )

    server_monitor = WindowsProcessTreeMonitor(mphserver_pids)
    server_monitor.sample()
    server_cpu_baseline = server_monitor.cpu_seconds() or 0.0
    server_working_set_baseline = server_monitor.current_working_set
    server_private_baseline = server_monitor.current_private
    env = dict(os.environ)
    prefdir = ROOT / "generated" / "matlab_prefs" / "busbar_multiphysics_benchmark"
    prefdir.mkdir(parents=True, exist_ok=True)
    env["MATLAB_PREFDIR"] = str(prefdir)
    startup = f"run('{_quote_matlab(runner_path)}')"
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    started = time.perf_counter()
    timed_out = False
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.Popen(
            [str(matlab), "-batch", startup],
            cwd=output_dir,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=flags if sys.platform == "win32" else 0,
        )
        matlab_monitor = WindowsProcessTreeMonitor(process.pid)
        combined_peak_working_set = 0
        combined_peak_private = 0
        combined_peak_process_count = 0
        while process.poll() is None:
            matlab_monitor.sample()
            server_monitor.sample()
            combined_peak_working_set = max(combined_peak_working_set, matlab_monitor.current_working_set + server_monitor.current_working_set)
            combined_peak_private = max(combined_peak_private, matlab_monitor.current_private + server_monitor.current_private)
            combined_peak_process_count = max(combined_peak_process_count, matlab_monitor.current_process_count + server_monitor.current_process_count)
            if time.perf_counter() - started > args.timeout_seconds:
                timed_out = True
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
            time.sleep(0.25)
        process.wait(timeout=30)
        matlab_monitor.sample()
        server_monitor.sample()
    wall_seconds = time.perf_counter() - started
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    if timed_out or process.returncode != 0 or "BUSBAR_SWEEP_SUCCESS" not in log_text or not csv_path.is_file() or not model_path.is_file():
        raise RuntimeError(f"3D busbar sweep failed; timed_out={timed_out}, return_code={process.returncode}, log={log_path}")

    rows = _read_rows(csv_path)
    physics = _physics_checks(
        rows,
        voltages_mv=voltages_mv,
        heat_transfer_coefficients=heat_transfer_coefficients,
    )
    if not physics["all_passed"]:
        raise RuntimeError(f"3D busbar sweep physics validation failed: {physics}")
    solve_seconds = [row["solve_seconds"] for row in rows]
    matlab_cpu = matlab_monitor.cpu_seconds() or 0.0
    server_cpu = max(0.0, (server_monitor.cpu_seconds() or 0.0) - server_cpu_baseline)
    historical_comparison = _historical_dense_comparison(rows) if args.grid == "dense49" else None
    if historical_comparison is not None and not historical_comparison["all_passed"]:
        raise RuntimeError(f"Historical dense sweep comparison failed: {historical_comparison}")
    report = {
        "kind": f"complete_3d_busbar_multiphysics_{args.grid}_sweep_benchmark",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "model": {
            "name": "busbar_joule_heat_baseline",
            "dimension": "3D",
            "physics": ["Electric Currents", "Heat Transfer in Solids", "Joule Heating multiphysics coupling"],
            "source_mph": str(SOURCE_MODEL.relative_to(ROOT)),
            "source_mph_size_bytes": SOURCE_MODEL.stat().st_size,
            "parameter_grid": {
                "Vtot_mV": list(voltages_mv),
                "htc_W_m2K": list(heat_transfer_coefficients),
            },
        },
        "execution": {
            "completed_cases": len(rows),
            "wall_seconds": wall_seconds,
            "sum_case_solve_seconds": sum(solve_seconds),
            "per_case_solve_seconds_median": statistics.median(solve_seconds),
            "per_case_solve_seconds_mean": statistics.fmean(solve_seconds),
            "per_case_solve_seconds_min": min(solve_seconds),
            "per_case_solve_seconds_max": max(solve_seconds),
            "per_case_solve_seconds_p95": _percentile(solve_seconds, 0.95),
            "matlab_process_cpu_seconds": matlab_cpu,
            "mphserver_process_cpu_seconds_during_sweep": server_cpu,
            "combined_matlab_mphserver_cpu_seconds": matlab_cpu + server_cpu,
        },
        "resources": {
            "matlab_peak_working_set_mb": matlab_monitor.peak_working_set / (1024 * 1024),
            "matlab_peak_private_memory_mb": matlab_monitor.peak_private / (1024 * 1024),
            "mphserver_baseline_working_set_mb": server_working_set_baseline / (1024 * 1024),
            "mphserver_peak_working_set_mb": server_monitor.peak_working_set / (1024 * 1024),
            "mphserver_working_set_increase_mb": max(0, server_monitor.peak_working_set - server_working_set_baseline) / (1024 * 1024),
            "mphserver_baseline_private_memory_mb": server_private_baseline / (1024 * 1024),
            "mphserver_peak_private_memory_mb": server_monitor.peak_private / (1024 * 1024),
            "mphserver_private_memory_increase_mb": max(0, server_monitor.peak_private - server_private_baseline) / (1024 * 1024),
            "combined_peak_working_set_mb": combined_peak_working_set / (1024 * 1024),
            "combined_peak_private_memory_mb": combined_peak_private / (1024 * 1024),
            "combined_process_tree_peak_count": combined_peak_process_count,
        },
        "validation": {
            **physics,
            "historical_dense_csv_comparison": historical_comparison,
        },
        "artifacts": {
            "csv": str(csv_path.relative_to(ROOT)),
            "final_mph": str(model_path.relative_to(ROOT)),
            "runner": str(runner_path.relative_to(ROOT)),
            "log": str(log_path.relative_to(ROOT)),
        },
        "rows": rows,
        "limitations": [
            "The benchmark covers a fixed 3D geometry, materials, mesh, boundary selections, and stationary solver on one workstation.",
            "Resource counters include the launched MATLAB tree and persistent mphserver tree; unrelated operating-system processes are excluded.",
            (
                "This is the complete 49-point surrogate-training grid."
                if args.grid == "dense49"
                else "The nine-point grid is a complete verification sweep but is smaller than the separate 49-point surrogate-training data set."
            ),
        ],
    }
    report_name = (
        "busbar_dense_multiphysics_sweep_benchmark.json"
        if args.grid == "dense49"
        else "busbar_multiphysics_sweep_benchmark.json"
    )
    report_path = output_dir / report_name
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
