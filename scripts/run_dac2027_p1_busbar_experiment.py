from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "dac2027" / "p1" / "experiments" / "busbar_power_delivery_design"
MANIFEST = ROOT / "configs" / "dac2027_p1_experiment_manifest.json"
BASELINE_CSV = ROOT / "generated" / "p3" / "current_drive_baseline" / "busbar_current_drive_baseline.csv"


def q(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def experiment_spec() -> tuple[dict, dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    experiment = next(row for row in manifest["experiments"] if row["scenario_id"] == "busbar_power_delivery_design")
    return manifest, experiment


def prepare_inputs(experiment: dict) -> Path:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "input_points.csv"
    pd.DataFrame(experiment["points"]).to_csv(path, index=False)
    return path


def build_runner(node: dict, experiment: dict, input_path: Path) -> Path:
    source = ROOT / experiment["source_mph"]
    runner = OUTPUT / "run_busbar_p1_post_freeze.m"
    result_csv = OUTPUT / "results.csv"
    mph_path = OUTPUT / "busbar_p1_post_freeze_final.mph"
    error_path = OUTPUT / "run.error.txt"
    script = f"""addpath('{str(node['livelink_matlab_path']).replace(chr(92), '/')}');
mphstart('{node.get('comsol_server_host', 'localhost')}', {int(node.get('comsol_server_port', 2036))});
model = mphopen('{q(source)}');
design = readtable('{q(input_path)}', 'VariableNamingRule', 'preserve');
output_csv = '{q(result_csv)}';
output_mph = '{q(mph_path)}';
error_path = '{q(error_path)}';
if isfile(error_path), delete(error_path); end
result = table();
for index = 1:height(design)
  case_id = string(design.case_id(index));
  L_mm = design.L_mm(index); wbb_mm = design.wbb_mm(index); tbb_mm = design.tbb_mm(index); bolt_radius_mm = design.bolt_radius_mm(index);
  I_load_A = design.I_load_A(index); htc_W_m2K = design.htc_W_m2K(index); T_amb_K = design.T_amb_K(index);
  model.param.set('L', sprintf('%.12g[mm]', L_mm));
  model.param.set('wbb', sprintf('%.12g[mm]', wbb_mm));
  model.param.set('tbb', sprintf('%.12g[mm]', tbb_mm));
  model.param.set('rad_1', sprintf('%.12g[mm]', bolt_radius_mm));
  model.param.set('I_load', sprintf('%.12g[A]', I_load_A));
  model.param.set('htc', sprintf('%.12g[W/(m^2*K)]', htc_W_m2K));
  model.param.set('T_amb', sprintf('%.12g[K]', T_amb_K));
  case_timer = tic;
  try
    model.component('comp1').geom('geom1').run;
    model.component('comp1').mesh('mesh1').run;
    model.study('std1').run;
    solve_seconds = toc(case_timer);
    terminal_selection = mphgetselection(model.component('comp1').physics('ec').feature('term1'));
    convection_selection = mphgetselection(model.component('comp1').physics('ht').feature('hf1'));
    tmax_k = mphmax(model, 'T', 3);
    tavg_k = mphmean(model, 'T', 3);
    jmax_a_m2 = mphmax(model, 'ec.normJ', 3);
    terminal_current_a = abs(mphint2(model, 'ec.nJ', 2, 'selection', terminal_selection.entities'));
    voltage_drop_mv = abs(mphmean(model, 'V', 2, 'selection', terminal_selection.entities'))*1000;
    joule_power_w = mphint2(model, 'ec.Qh', 3);
    convection_power_w = abs(mphint2(model, 'ht.nteflux', 2, 'selection', convection_selection.entities'));
    energy_imbalance_percent = abs(joule_power_w-convection_power_w)/joule_power_w*100;
    copper_volume_m3 = mphint2(model, '1', 3, 'selection', 1);
    copper_mass_kg = copper_volume_m3*8960;
    solver_status = string('solved'); error_message = string('');
  catch caseError
    solve_seconds = toc(case_timer);
    tmax_k = NaN; tavg_k = NaN; jmax_a_m2 = NaN; terminal_current_a = NaN; voltage_drop_mv = NaN;
    joule_power_w = NaN; convection_power_w = NaN; energy_imbalance_percent = NaN; copper_volume_m3 = NaN; copper_mass_kg = NaN;
    solver_status = string('failed'); error_message = string(caseError.message);
  end
  next_row = table(case_id, L_mm, wbb_mm, tbb_mm, bolt_radius_mm, I_load_A, htc_W_m2K, T_amb_K, tmax_k, tavg_k, jmax_a_m2, terminal_current_a, voltage_drop_mv, joule_power_w, convection_power_w, energy_imbalance_percent, copper_volume_m3, copper_mass_kg, solve_seconds, solver_status, error_message, ...
    'VariableNames', {{'case_id','L_mm','wbb_mm','tbb_mm','bolt_radius_mm','I_load_A','htc_W_m2K','T_amb_K','Tmax_K','Tavg_K','Jmax_A_m2','terminal_current_A','voltage_drop_mV','joule_power_W','convection_power_W','energy_imbalance_percent','copper_volume_m3','copper_mass_kg','solve_seconds','solver_status','error_message'}});
  result = [result; next_row]; %#ok<AGROW>
  writetable(result, output_csv);
  fprintf('DAC_P1_BUSBAR_CASE %d/%d %s status=%s solve_seconds=%.6f\\n', index, height(design), case_id, solver_status, solve_seconds);
end
mphsave(model, output_mph);
fprintf('DAC_P1_BUSBAR_FINISHED cases=%d failed=%d\\n', height(result), sum(string(result.solver_status) ~= 'solved'));
"""
    runner.write_text(script, encoding="utf-8")
    return runner


def artifact(path: Path) -> dict:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "exists": path.is_file(),
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "sha256": sha256(path) if path.is_file() else "",
    }


def record(row: pd.Series) -> dict:
    return {str(key): (None if pd.isna(value) else value) for key, value in row.to_dict().items()}


def evaluate(manifest: dict, experiment: dict, elapsed: float) -> dict:
    input_path = OUTPUT / "input_points.csv"
    result_path = OUTPUT / "results.csv"
    mph_path = OUTPUT / "busbar_p1_post_freeze_final.mph"
    log_path = OUTPUT / "matlab_stdout.log"
    baseline = pd.read_csv(BASELINE_CSV).iloc[0]
    baseline_jmax = float(baseline["Jmax_A_m2"])
    frame = pd.read_csv(result_path)
    limits = experiment["thresholds"]
    frame["normalized_voltage_at_160A_mV"] = frame["voltage_drop_mV"] * 160.0 / frame["I_load_A"]
    frame["terminal_current_relative_error"] = (frame["terminal_current_A"] - frame["I_load_A"]).abs() / frame["I_load_A"]
    frame["terminal_current_passed"] = frame["terminal_current_relative_error"] <= limits["terminal_current_relative_error_max"]
    frame["energy_balance_passed"] = frame["energy_imbalance_percent"] <= limits["energy_imbalance_percent_max"]
    frame["temperature_passed"] = frame["Tmax_K"] <= limits["Tmax_K_max"]
    frame["voltage_passed"] = frame["normalized_voltage_at_160A_mV"] <= limits["normalized_voltage_at_160A_mV_max"]
    frame["current_density_passed"] = frame["Jmax_A_m2"] <= limits["Jmax_ratio_to_baseline_max"] * baseline_jmax * frame["I_load_A"] / 160.0
    frame["geometry_passed"] = frame["bolt_radius_mm"] <= limits["bolt_radius_to_width_max"] * frame["wbb_mm"]
    frame["all_gates_passed"] = frame[["terminal_current_passed", "energy_balance_passed", "temperature_passed", "voltage_passed", "current_density_passed", "geometry_passed"]].all(axis=1) & frame["solver_status"].eq("solved")
    evaluated = OUTPUT / "evaluated_results.csv"
    frame.to_csv(evaluated, index=False)
    feasible = frame[frame["all_gates_passed"]].sort_values(["joule_power_W", "copper_mass_kg", "case_id"])
    selected = record(feasible.iloc[0]) if len(feasible) else None
    tradeoff = record(feasible.sort_values(["copper_mass_kg", "joule_power_W", "case_id"]).iloc[0]) if len(feasible) else None
    checks = {
        "manifest_frozen_before_run": datetime.fromisoformat(manifest["frozen_at"]).astimezone(timezone.utc) <= datetime.now(timezone.utc),
        "all_declared_points_recorded": len(frame) == len(experiment["points"]) and set(frame["case_id"]) == {row["case_id"] for row in experiment["points"]},
        "all_comsol_solves_succeeded": bool(frame["solver_status"].eq("solved").all()),
        "all_physical_validation_passed": bool(frame[["terminal_current_passed", "energy_balance_passed"]].all(axis=None)),
        "at_least_one_design_feasible": bool(frame["all_gates_passed"].any()),
        "decision_selected_by_frozen_rule": selected is not None,
        "fresh_mph_created": mph_path.is_file() and mph_path.stat().st_size > 0,
    }
    artifacts = {name: artifact(path) for name, path in {
        "manifest": MANIFEST,
        "input_csv": input_path,
        "result_csv": result_path,
        "evaluated_csv": evaluated,
        "mph": mph_path,
        "matlab_runner": OUTPUT / "run_busbar_p1_post_freeze.m",
        "matlab_log": log_path,
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
        "minimum_mass_tradeoff": tradeoff,
        "checks": checks,
        "passed": all(checks.values()),
        "wall_seconds": elapsed,
        "artifacts": artifacts,
        "claim_boundary": "This run verifies two frozen nominal-condition design candidates. It is not a product qualification or robustness test over the full operating range.",
    }


def main() -> int:
    manifest, experiment = experiment_spec()
    node = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    input_path = prepare_inputs(experiment)
    runner = build_runner(node, experiment, input_path)
    matlab = Path(node["matlab_executable"])
    if not matlab.is_file():
        raise FileNotFoundError(f"MATLAB executable not found: {matlab}")
    started = time.perf_counter()
    completed = subprocess.run(
        [str(matlab), "-batch", f"run('{q(runner)}')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=int(node.get("timeout_seconds", 3600)),
    )
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
