from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from comsol_small_model.eda_design import pareto_front


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "p3" / "pareto_verification"
INPUT = ROOT / "generated" / "p3" / "optimization" / "fresh_pareto_verification_inputs.csv"
SOURCE_MPH = ROOT / "generated" / "p3" / "current_drive_baseline" / "busbar_current_drive_baseline.mph"
BASELINE_MASS = 0.414389458520742
BASELINE_POWER = 3.17079395640271
BASELINE_JMAX = 5_141_738.84968363


def q(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def build_runner(node: dict) -> Path:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    runner = OUTPUT / "run_fresh_pareto_verification.m"
    csv_path = OUTPUT / "fresh_pareto_verification_results.csv"
    mph_path = OUTPUT / "fresh_pareto_verification_final.mph"
    script = f"""addpath('{str(node['livelink_matlab_path']).replace(chr(92), '/')}');
mphstart('{node.get('comsol_server_host', 'localhost')}', {int(node.get('comsol_server_port', 2036))});
model = mphopen('{q(SOURCE_MPH)}');
design = readtable('{q(INPUT)}', 'VariableNamingRule', 'preserve');
output_csv = '{q(csv_path)}';
output_mph = '{q(mph_path)}';
result = table();
for index = 1:height(design)
  case_id = string(design.case_id(index));
  L_mm = design.L_mm(index); wbb_mm = design.wbb_mm(index); tbb_mm = design.tbb_mm(index); bolt_radius_mm = design.bolt_radius_mm(index);
  I_load_A = design.I_load_A(index); htc_W_m2K = design.htc_W_m2K(index); T_amb_K = design.T_amb_K(index);
  model.param.set('L', sprintf('%.12g[mm]', L_mm)); model.param.set('wbb', sprintf('%.12g[mm]', wbb_mm));
  model.param.set('tbb', sprintf('%.12g[mm]', tbb_mm)); model.param.set('rad_1', sprintf('%.12g[mm]', bolt_radius_mm));
  model.param.set('I_load', sprintf('%.12g[A]', I_load_A)); model.param.set('htc', sprintf('%.12g[W/(m^2*K)]', htc_W_m2K));
  model.param.set('T_amb', sprintf('%.12g[K]', T_amb_K));
  case_timer = tic;
  model.component('comp1').geom('geom1').run; model.component('comp1').mesh('mesh1').run; model.study('std1').run;
  solve_seconds = toc(case_timer);
  terminal_selection = mphgetselection(model.component('comp1').physics('ec').feature('term1'));
  convection_selection = mphgetselection(model.component('comp1').physics('ht').feature('hf1'));
  Tmax_K = mphmax(model, 'T', 3); Tavg_K = mphmean(model, 'T', 3); Jmax_A_m2 = mphmax(model, 'ec.normJ', 3);
  terminal_current_A = abs(mphint2(model, 'ec.nJ', 2, 'selection', terminal_selection.entities'));
  voltage_drop_mV = abs(mphmean(model, 'V', 2, 'selection', terminal_selection.entities'))*1000;
  joule_power_W = mphint2(model, 'ec.Qh', 3);
  convection_power_W = abs(mphint2(model, 'ht.nteflux', 2, 'selection', convection_selection.entities'));
  energy_imbalance_percent = abs(joule_power_W-convection_power_W)/joule_power_W*100;
  copper_volume_m3 = mphint2(model, '1', 3, 'selection', 1); copper_mass_kg = copper_volume_m3*8960;
  solver_status = string('solved');
  next_row = table(case_id,L_mm,wbb_mm,tbb_mm,bolt_radius_mm,I_load_A,htc_W_m2K,T_amb_K,Tmax_K,Tavg_K,Jmax_A_m2,terminal_current_A,voltage_drop_mV,joule_power_W,convection_power_W,energy_imbalance_percent,copper_volume_m3,copper_mass_kg,solve_seconds,solver_status, ...
    'VariableNames', {{'case_id','L_mm','wbb_mm','tbb_mm','bolt_radius_mm','I_load_A','htc_W_m2K','T_amb_K','Tmax_K','Tavg_K','Jmax_A_m2','terminal_current_A','voltage_drop_mV','joule_power_W','convection_power_W','energy_imbalance_percent','copper_volume_m3','copper_mass_kg','solve_seconds','solver_status'}});
  result = [result; next_row]; %#ok<AGROW>
  writetable(result, output_csv);
  fprintf('P3_PARETO_VERIFY %d/%d %s solve_seconds=%.6f\\n', index, height(design), case_id, solve_seconds);
end
mphsave(model, output_mph);
fprintf('P3_PARETO_VERIFY_SUCCESS cases=%d\\n', height(result));
"""
    runner.write_text(script, encoding="utf-8")
    return runner


def validate(elapsed: float) -> dict:
    proposed = pd.read_csv(INPUT)
    actual = pd.read_csv(OUTPUT / "fresh_pareto_verification_results.csv")
    proposal_columns = [
        "case_id", "verification_policy",
        *[name for name in proposed.columns if name.startswith("pred_") or name.startswith("std_")],
    ]
    merged = actual.merge(proposed[proposal_columns], on="case_id", how="inner")
    merged["temperature_constraint_passed"] = merged["Tmax_K"] <= 373.15
    merged["voltage_constraint_passed"] = merged["voltage_drop_mV"] <= 20.0
    merged["current_density_constraint_passed"] = merged["Jmax_A_m2"] <= 1.10 * BASELINE_JMAX
    merged["geometry_constraint_passed"] = merged["bolt_radius_mm"] <= 0.2 * merged["wbb_mm"] + 1e-12
    merged["constraints_passed"] = merged[["temperature_constraint_passed", "voltage_constraint_passed", "current_density_constraint_passed", "geometry_constraint_passed"]].all(axis=1)
    merged["comsol_verified"] = True
    for target in ("Tmax_K", "Jmax_A_m2", "joule_power_W", "copper_mass_kg"):
        merged[f"absolute_error_{target}"] = (merged[target] - merged[f"pred_{target}"]).abs()
    merged["improves_both_baseline_objectives"] = (merged["copper_mass_kg"] < BASELINE_MASS) & (merged["joule_power_W"] < BASELINE_POWER)
    verified_pareto = pareto_front(merged, objectives=("copper_mass_kg", "joule_power_W"))
    evaluated_path = OUTPUT / "fresh_pareto_verification_evaluated.csv"
    pareto_path = OUTPUT / "verified_pareto.csv"
    merged.to_csv(evaluated_path, index=False)
    verified_pareto.to_csv(pareto_path, index=False)
    training = pd.read_csv(ROOT / "generated" / "p3" / "initial_design" / "busbar_p3_initial_design_evaluated.csv")
    features = ["L_mm", "wbb_mm", "tbb_mm", "bolt_radius_mm", "I_load_A", "htc_W_m2K", "T_amb_K"]
    overlap = set(map(tuple, training[features].round(10).to_numpy())) & set(map(tuple, merged[features].round(10).to_numpy()))
    checks = {
        "all_five_candidates_solved": bool(len(merged) == len(proposed) == 5 and merged["solver_status"].eq("solved").all()),
        "fresh_candidates_do_not_overlap_training": not overlap,
        "terminal_current_within_1_percent": bool(((merged["terminal_current_A"] - 160.0).abs() <= 1.6).all()),
        "energy_imbalance_below_0_1_percent": bool((merged["energy_imbalance_percent"] <= 0.1).all()),
        "at_least_one_feasible_verified_candidate": bool(merged["constraints_passed"].any()),
        "at_least_one_feasible_dual_objective_improvement": bool((merged["constraints_passed"] & merged["improves_both_baseline_objectives"]).any()),
    }
    report = {
        "schema": "comsol-p3-fresh-pareto-verification",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(merged),
        "feasible_count": int(merged["constraints_passed"].sum()),
        "verified_pareto_count": len(verified_pareto),
        "dual_objective_improvement_count": int((merged["constraints_passed"] & merged["improves_both_baseline_objectives"]).sum()),
        "checks": checks,
        "passed": all(checks.values()),
        "prediction_errors": {
            target: {
                "mae": float(merged[f"absolute_error_{target}"].mean()),
                "max_absolute_error": float(merged[f"absolute_error_{target}"].max()),
            }
            for target in ("Tmax_K", "Jmax_A_m2", "joule_power_W", "copper_mass_kg")
        },
        "wall_seconds": elapsed,
        "artifacts": {"evaluated": str(evaluated_path.relative_to(ROOT)), "verified_pareto": str(pareto_path.relative_to(ROOT)), "mph": str((OUTPUT / "fresh_pareto_verification_final.mph").relative_to(ROOT))},
        "scope": "Fresh COMSOL verification closes the candidate loop for five nominal-condition proposals. The reserved 60-point final domain test remains untouched.",
    }
    (OUTPUT / "pareto_verification_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    node = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    runner = build_runner(node)
    started = time.perf_counter()
    result = subprocess.run([str(Path(node["matlab_executable"])), "-batch", f"run('{q(runner)}')"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=int(node.get("timeout_seconds", 3600)))
    (OUTPUT / "matlab_stdout.log").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"MATLAB returned {result.returncode}; see {OUTPUT / 'matlab_stdout.log'}")
    report = validate(time.perf_counter() - started)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

