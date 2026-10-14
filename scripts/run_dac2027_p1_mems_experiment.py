from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "dac2027" / "p1" / "experiments" / "mems_thermal_actuator_operating_design"
MANIFEST = ROOT / "configs" / "dac2027_p1_experiment_manifest.json"


def q(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact(path: Path) -> dict:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "exists": path.is_file(),
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "sha256": sha256(path) if path.is_file() else "",
    }


def record(row: pd.Series) -> dict:
    return {str(key): (None if pd.isna(value) else value) for key, value in row.to_dict().items()}


def spec() -> tuple[dict, dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    experiment = next(row for row in manifest["experiments"] if row["scenario_id"] == "mems_thermal_actuator_operating_design")
    return manifest, experiment


def resolve_source(experiment: dict) -> Path:
    for candidate in experiment["source_mph_candidates"]:
        path = Path(candidate)
        if not path.is_absolute():
            path = ROOT / path
        if path.is_file():
            return path
    searched = "; ".join(experiment["source_mph_candidates"])
    raise FileNotFoundError(f"MEMS source MPH is unavailable. Searched: {searched}")


def build_runner(node: dict, source: Path, input_path: Path) -> Path:
    runner = OUTPUT / "run_mems_p1_post_freeze.m"
    result_path = OUTPUT / "results.csv"
    mph_path = OUTPUT / "mems_p1_post_freeze_final.mph"
    error_path = OUTPUT / "run.error.txt"
    runner.write_text(f"""addpath('{str(node['livelink_matlab_path']).replace(chr(92), '/')}');
mphstart('{node.get('comsol_server_host', 'localhost')}', {int(node.get('comsol_server_port', 2036))});
model = mphopen('{q(source)}');
design = readtable('{q(input_path)}', 'VariableNamingRule', 'preserve');
output_csv = '{q(result_path)}'; output_mph = '{q(mph_path)}'; error_path = '{q(error_path)}';
if isfile(error_path), delete(error_path); end
result = table();
for index = 1:height(design)
  case_id = string(design.case_id(index)); DV_V = design.DV_V(index); htc_s_W_m2K = design.htc_s_W_m2K(index); htc_us_W_m2K = design.htc_us_W_m2K(index);
  model.param.set('DV', sprintf('%.12g[V]', DV_V));
  model.param.set('htc_s', sprintf('%.12g[W/(m^2*K)]', htc_s_W_m2K));
  model.param.set('htc_us', sprintf('%.12g[W/(m^2*K)]', htc_us_W_m2K));
  case_timer = tic;
  try
    model.study('std1').run;
    solve_seconds = toc(case_timer);
    Tmax_K = mphmax(model, 'T', 3); umax_m = mphmax(model, 'solid.disp', 3, 'unit', 'm'); joule_power_W = mphint2(model, 'ec.Qh', 3);
    solver_status = string('solved'); error_message = string('');
  catch caseError
    solve_seconds = toc(case_timer); Tmax_K = NaN; umax_m = NaN; joule_power_W = NaN;
    solver_status = string('failed'); error_message = string(caseError.message);
  end
  next_row = table(case_id, DV_V, htc_s_W_m2K, htc_us_W_m2K, Tmax_K, umax_m, joule_power_W, solve_seconds, solver_status, error_message, ...
    'VariableNames', {{'case_id','DV_V','htc_s_W_m2K','htc_us_W_m2K','Tmax_K','umax_m','joule_power_W','solve_seconds','solver_status','error_message'}});
  result = [result; next_row]; %#ok<AGROW>
  writetable(result, output_csv);
  fprintf('DAC_P1_MEMS_CASE %d/%d %s status=%s solve_seconds=%.6f\\n', index, height(design), case_id, solver_status, solve_seconds);
end
mphsave(model, output_mph);
fprintf('DAC_P1_MEMS_FINISHED cases=%d failed=%d\\n', height(result), sum(string(result.solver_status) ~= 'solved'));
""", encoding="utf-8")
    return runner


def evaluate(manifest: dict, experiment: dict, elapsed: float) -> dict:
    frame = pd.read_csv(OUTPUT / "results.csv")
    limits = experiment["thresholds"]
    frame["temperature_passed"] = frame["Tmax_K"] <= limits["Tmax_K_max"]
    frame["displacement_passed"] = frame["umax_m"] >= limits["umax_m_min"]
    frame["power_passed"] = frame["joule_power_W"] <= limits["joule_power_W_max"]
    frame["all_gates_passed"] = frame[["temperature_passed", "displacement_passed", "power_passed"]].all(axis=1) & frame["solver_status"].eq("solved")
    evaluated = OUTPUT / "evaluated_results.csv"
    frame.to_csv(evaluated, index=False)
    feasible = frame[frame["all_gates_passed"]].sort_values(["umax_m", "joule_power_W", "DV_V"], ascending=[False, True, True])
    selected = record(feasible.iloc[0]) if len(feasible) else None
    mph_path = OUTPUT / "mems_p1_post_freeze_final.mph"
    checks = {
        "all_declared_points_recorded": len(frame) == len(experiment["points"]) and set(frame["case_id"]) == {row["case_id"] for row in experiment["points"]},
        "all_comsol_solves_succeeded": bool(frame["solver_status"].eq("solved").all()),
        "at_least_one_design_feasible": bool(frame["all_gates_passed"].any()),
        "decision_selected_by_frozen_rule": selected is not None,
        "fresh_mph_created": mph_path.is_file() and mph_path.stat().st_size > 0,
    }
    artifacts = {name: artifact(path) for name, path in {
        "manifest": MANIFEST,
        "input_csv": OUTPUT / "input_points.csv",
        "result_csv": OUTPUT / "results.csv",
        "evaluated_csv": evaluated,
        "mph": mph_path,
        "matlab_runner": OUTPUT / "run_mems_p1_post_freeze.m",
        "matlab_log": OUTPUT / "matlab_stdout.log",
    }.items()}
    return {
        "schema": "dac2027-p1-post-freeze-comsol-experiment",
        "schemaVersion": "1.0.0",
        "scenario_id": experiment["scenario_id"],
        "manifest_frozen_at": manifest["frozen_at"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_type": "fresh_post_p1_freeze_comsol",
        "point_count": len(frame),
        "feasible_count": int(frame["all_gates_passed"].sum()),
        "selection_rule": experiment["selection_rule"],
        "selected_design": selected,
        "checks": checks,
        "passed": all(checks.values()),
        "wall_seconds": elapsed,
        "artifacts": artifacts,
        "claim_boundary": "This four-point frozen grid verifies operating-point selection for one preserved MEMS model; it does not establish process-corner or fabricated-device reliability.",
    }


def main() -> int:
    manifest, experiment = spec()
    source = resolve_source(experiment)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    input_path = OUTPUT / "input_points.csv"
    pd.DataFrame(experiment["points"]).to_csv(input_path, index=False)
    node = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    runner = build_runner(node, source, input_path)
    started = time.perf_counter()
    completed = subprocess.run([str(Path(node["matlab_executable"])), "-batch", f"run('{q(runner)}')"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=int(node.get("timeout_seconds", 3600)))
    (OUTPUT / "matlab_stdout.log").write_text(completed.stdout + "\n" + completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"MATLAB returned {completed.returncode}; see {OUTPUT / 'matlab_stdout.log'}")
    report = evaluate(manifest, experiment, time.perf_counter() - started)
    report_path = OUTPUT / "report.json"
    report["artifacts"]["report"] = {"path": report_path.relative_to(ROOT).as_posix(), "exists": True}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": report_path.relative_to(ROOT).as_posix(), "passed": report["passed"], "selected_design": report["selected_design"]}, ensure_ascii=False, indent=2, default=str))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
