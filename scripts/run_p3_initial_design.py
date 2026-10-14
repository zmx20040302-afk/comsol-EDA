from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "p3" / "initial_design"
INPUT = ROOT / "generated" / "p3" / "designs" / "initial_design_inputs.csv"
SOURCE_MPH = ROOT / "generated" / "p3" / "current_drive_baseline" / "busbar_current_drive_baseline.mph"


def q(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def build_runner(node: dict) -> Path:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    runner = OUTPUT / "run_busbar_p3_initial_design.m"
    csv_path = OUTPUT / "busbar_p3_initial_design_results.csv"
    mph_path = OUTPUT / "busbar_p3_initial_design_final.mph"
    error_path = OUTPUT / "busbar_p3_initial_design.error.txt"
    script = f"""addpath('{str(node['livelink_matlab_path']).replace(chr(92), '/')}');
mphstart('{node.get('comsol_server_host', 'localhost')}', {int(node.get('comsol_server_port', 2036))});
model = mphopen('{q(SOURCE_MPH)}');
design = readtable('{q(INPUT)}', 'VariableNamingRule', 'preserve');
output_csv = '{q(csv_path)}';
output_mph = '{q(mph_path)}';
error_path = '{q(error_path)}';
if isfile(error_path), delete(error_path); end
if isfile(output_csv)
  result = readtable(output_csv, 'VariableNamingRule', 'preserve');
else
  result = table();
end
for index = 1:height(design)
  case_id = string(design.case_id(index));
  if ~isempty(result) && any(string(result.case_id) == case_id)
    fprintf('P3_INITIAL_SKIP %s\\n', case_id);
    continue;
  end
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
    solver_status = string('solved');
    error_message = string('');
  catch caseError
    solve_seconds = toc(case_timer);
    tmax_k = NaN; tavg_k = NaN; jmax_a_m2 = NaN; terminal_current_a = NaN; voltage_drop_mv = NaN;
    joule_power_w = NaN; convection_power_w = NaN; energy_imbalance_percent = NaN; copper_volume_m3 = NaN; copper_mass_kg = NaN;
    solver_status = string('failed');
    error_message = string(caseError.message);
  end
  next_row = table(case_id, L_mm, wbb_mm, tbb_mm, bolt_radius_mm, I_load_A, htc_W_m2K, T_amb_K, tmax_k, tavg_k, jmax_a_m2, terminal_current_a, voltage_drop_mv, joule_power_w, convection_power_w, energy_imbalance_percent, copper_volume_m3, copper_mass_kg, solve_seconds, solver_status, error_message, ...
    'VariableNames', {{'case_id','L_mm','wbb_mm','tbb_mm','bolt_radius_mm','I_load_A','htc_W_m2K','T_amb_K','Tmax_K','Tavg_K','Jmax_A_m2','terminal_current_A','voltage_drop_mV','joule_power_W','convection_power_W','energy_imbalance_percent','copper_volume_m3','copper_mass_kg','solve_seconds','solver_status','error_message'}});
  result = [result; next_row]; %#ok<AGROW>
  writetable(result, output_csv);
  fprintf('P3_INITIAL_CASE %d/%d %s status=%s solve_seconds=%.6f\\n', index, height(design), case_id, solver_status, solve_seconds);
end
mphsave(model, output_mph);
failed = sum(string(result.solver_status) ~= 'solved');
fprintf('P3_INITIAL_DESIGN_FINISHED cases=%d failed=%d\\n', height(result), failed);
"""
    runner.write_text(script, encoding="utf-8")
    return runner


def validate(elapsed: float) -> dict:
    spec = json.loads((ROOT / "configs" / "busbar_eda_design_problem.json").read_text(encoding="utf-8"))
    csv_path = OUTPUT / "busbar_p3_initial_design_results.csv"
    frame = pd.read_csv(csv_path)
    solved = frame["solver_status"].astype(str).eq("solved")
    baseline_jmax = 5_141_738.84968363
    numeric = frame.loc[solved].copy()
    numeric["temperature_constraint_passed"] = numeric["Tmax_K"] <= 373.15
    numeric["normalized_voltage_at_160A_mV"] = numeric["voltage_drop_mV"] * 160.0 / numeric["I_load_A"]
    numeric["voltage_constraint_passed"] = numeric["normalized_voltage_at_160A_mV"] <= 20.0
    numeric["current_density_constraint_passed"] = numeric["Jmax_A_m2"] <= 1.10 * baseline_jmax * numeric["I_load_A"] / 160.0
    numeric["geometry_constraint_passed"] = numeric["bolt_radius_mm"] <= 0.2 * numeric["wbb_mm"] + 1e-12
    numeric["constraints_passed"] = numeric[[
        "temperature_constraint_passed", "voltage_constraint_passed",
        "current_density_constraint_passed", "geometry_constraint_passed",
    ]].all(axis=1)
    numeric["comsol_verified"] = True
    evaluated_path = OUTPUT / "busbar_p3_initial_design_evaluated.csv"
    numeric.to_csv(evaluated_path, index=False)
    checks = {
        "all_80_cases_recorded": len(frame) == 80,
        "all_cases_solved": bool(solved.all()),
        "terminal_current_within_1_percent": bool(((numeric["terminal_current_A"] - numeric["I_load_A"]).abs() <= 0.01 * numeric["I_load_A"]).all()),
        "energy_imbalance_below_0_1_percent": bool((numeric["energy_imbalance_percent"] <= 0.1).all()),
        "all_numeric_outputs_finite": bool(numeric[[
            "Tmax_K", "Tavg_K", "Jmax_A_m2", "terminal_current_A", "voltage_drop_mV",
            "joule_power_W", "convection_power_W", "energy_imbalance_percent",
            "copper_volume_m3", "copper_mass_kg", "solve_seconds",
        ]].notna().all().all()),
        "independent_holdout_remains_unsolved": not (ROOT / "generated" / "p3" / "holdout" / "results.csv").exists(),
    }
    report = {
        "schema": "comsol-p3-initial-design-execution",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "design_rows": len(frame),
        "solved_rows": int(solved.sum()),
        "failed_rows": int((~solved).sum()),
        "checks": checks,
        "passed": all(checks.values()),
        "constraint_summary": {
            "feasible_rows": int(numeric["constraints_passed"].sum()),
            "infeasible_rows": int((~numeric["constraints_passed"]).sum()),
            "temperature_violations": int((~numeric["temperature_constraint_passed"]).sum()),
            "normalized_voltage_violations": int((~numeric["voltage_constraint_passed"]).sum()),
            "current_density_violations": int((~numeric["current_density_constraint_passed"]).sum()),
        },
        "ranges": {
            name: {"min": float(numeric[name].min()), "max": float(numeric[name].max())}
            for name in ("Tmax_K", "Jmax_A_m2", "voltage_drop_mV", "joule_power_W", "copper_mass_kg", "energy_imbalance_percent", "solve_seconds")
        },
        "wall_seconds": elapsed,
        "artifacts": {
            "inputs": str(INPUT.relative_to(ROOT)),
            "results": str(csv_path.relative_to(ROOT)),
            "evaluated_results": str(evaluated_path.relative_to(ROOT)),
            "final_mph": str((OUTPUT / "busbar_p3_initial_design_final.mph").relative_to(ROOT)),
        },
        "release_gate": "Use these rows for fitting only. The 60-point independent domain set and 20-point OOD set remain untouched until final evaluation.",
        "provisional_constraint_note": spec["constraints"][0]["note"],
    }
    (OUTPUT / "initial_design_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    node = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    if not INPUT.is_file():
        raise FileNotFoundError(f"P3 design input missing: {INPUT}")
    runner = build_runner(node)
    started = time.perf_counter()
    result = subprocess.run(
        [str(Path(node["matlab_executable"])), "-batch", f"run('{q(runner)}')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=int(node.get("timeout_seconds", 3600)),
    )
    (OUTPUT / "matlab_stdout.log").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"MATLAB returned {result.returncode}; see {OUTPUT / 'matlab_stdout.log'}")
    report = validate(time.perf_counter() - started)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

