from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "p3" / "geometry_smoke"
SOURCE_MPH = ROOT / "generated" / "p3" / "current_drive_baseline" / "busbar_current_drive_baseline.mph"


def q(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def cases_from_spec(spec: dict) -> list[dict]:
    baseline = spec["baseline"]
    base = {name: float(baseline[name]) for name in ("L_mm", "wbb_mm", "tbb_mm", "bolt_radius_mm")}
    cases = [{"case_id": "baseline", **base}]
    for variable in spec["decision_variables"]:
        name = variable["name"]
        for suffix, value in (("low", variable["lower"]), ("high", variable["upper"])):
            row = {"case_id": f"{name}_{suffix}", **base}
            row[name] = float(value)
            cases.append(row)
    return cases


def build_runner(node: dict, cases: list[dict]) -> Path:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    runner = OUTPUT / "run_busbar_geometry_smoke.m"
    csv_path = OUTPUT / "busbar_geometry_smoke.csv"
    mph_path = OUTPUT / "busbar_geometry_smoke_final.mph"
    error_path = OUTPUT / "busbar_geometry_smoke.error.txt"
    case_ids = " ".join(f"'{row['case_id']}'" for row in cases)
    arrays = {
        name: " ".join(f"{float(row[name]):.12g}" for row in cases)
        for name in ("L_mm", "wbb_mm", "tbb_mm", "bolt_radius_mm")
    }
    script = f"""addpath('{str(node['livelink_matlab_path']).replace(chr(92), '/')}');
mphstart('{node.get('comsol_server_host', 'localhost')}', {int(node.get('comsol_server_port', 2036))});
model = mphopen('{q(SOURCE_MPH)}');
case_ids = {{{case_ids}}};
L_values = [{arrays['L_mm']}];
w_values = [{arrays['wbb_mm']}];
t_values = [{arrays['tbb_mm']}];
r_values = [{arrays['bolt_radius_mm']}];
output_csv = '{q(csv_path)}';
output_mph = '{q(mph_path)}';
error_path = '{q(error_path)}';
if isfile(error_path), delete(error_path); end
result = table();
try
  for index = 1:numel(case_ids)
    model.param.set('L', sprintf('%.12g[mm]', L_values(index)));
    model.param.set('wbb', sprintf('%.12g[mm]', w_values(index)));
    model.param.set('tbb', sprintf('%.12g[mm]', t_values(index)));
    model.param.set('rad_1', sprintf('%.12g[mm]', r_values(index)));
    case_timer = tic;
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
    next_row = table(string(case_ids{{index}}), L_values(index), w_values(index), t_values(index), r_values(index), tmax_k, tavg_k, jmax_a_m2, terminal_current_a, voltage_drop_mv, joule_power_w, convection_power_w, energy_imbalance_percent, copper_volume_m3, copper_mass_kg, solve_seconds, solver_status, ...
      'VariableNames', {{'case_id','L_mm','wbb_mm','tbb_mm','bolt_radius_mm','Tmax_K','Tavg_K','Jmax_A_m2','terminal_current_A','voltage_drop_mV','joule_power_W','convection_power_W','energy_imbalance_percent','copper_volume_m3','copper_mass_kg','solve_seconds','solver_status'}});
    result = [result; next_row]; %#ok<AGROW>
    writetable(result, output_csv);
    fprintf('P3_GEOMETRY_CASE %d/%d %s solve_seconds=%.6f\\n', index, numel(case_ids), case_ids{{index}}, solve_seconds);
  end
  mphsave(model, output_mph);
  fprintf('P3_GEOMETRY_SMOKE_SUCCESS cases=%d\\n', height(result));
catch errorInfo
  error_file = fopen(error_path, 'w');
  fprintf(error_file, '%s\\n', getReport(errorInfo, 'extended', 'hyperlinks', 'off'));
  fclose(error_file);
  rethrow(errorInfo);
end
"""
    runner.write_text(script, encoding="utf-8")
    return runner


def validate(cases: list[dict], elapsed: float) -> dict:
    csv_path = OUTPUT / "busbar_geometry_smoke.csv"
    if not csv_path.is_file():
        error_path = OUTPUT / "busbar_geometry_smoke.error.txt"
        detail = error_path.read_text(encoding="utf-8", errors="replace") if error_path.is_file() else "missing CSV"
        raise RuntimeError(detail)
    frame = pd.read_csv(csv_path)
    baseline_jmax = float(frame.loc[frame["case_id"] == "baseline", "Jmax_A_m2"].iloc[0])
    frame["temperature_constraint_passed"] = frame["Tmax_K"] <= 373.15
    frame["voltage_constraint_passed"] = frame["voltage_drop_mV"] <= 20.0
    frame["current_density_constraint_passed"] = frame["Jmax_A_m2"] <= 1.10 * baseline_jmax
    frame["geometry_constraint_passed"] = frame["bolt_radius_mm"] <= 0.2 * frame["wbb_mm"] + 1e-12
    frame["constraints_passed"] = frame[[
        "temperature_constraint_passed", "voltage_constraint_passed",
        "current_density_constraint_passed", "geometry_constraint_passed",
    ]].all(axis=1)
    frame["comsol_verified"] = True
    evaluated_path = OUTPUT / "busbar_geometry_smoke_evaluated.csv"
    frame.to_csv(evaluated_path, index=False)
    checks = {
        "all_nine_cases_exported": len(frame) == len(cases) == 9,
        "all_solver_status_solved": set(frame["solver_status"].astype(str)) == {"solved"},
        "fixed_current_within_1_percent": bool(((frame["terminal_current_A"] - 160.0).abs() <= 1.6).all()),
        "energy_imbalance_below_0_1_percent": bool((frame["energy_imbalance_percent"] <= 0.1).all()),
        "geometry_rule_satisfied": bool((frame["bolt_radius_mm"] <= 0.2 * frame["wbb_mm"] + 1e-12).all()),
        "outputs_are_finite": bool(frame.select_dtypes(include="number").notna().all().all()),
        "constraint_classification_has_feasible_and_infeasible_cases": bool(frame["constraints_passed"].any() and (~frame["constraints_passed"]).any()),
    }
    report = {
        "schema": "comsol-p3-geometry-smoke",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(frame),
        "decision_variables_checked": ["L_mm", "wbb_mm", "tbb_mm", "bolt_radius_mm"],
        "checks": checks,
        "passed": all(checks.values()),
        "ranges": {
            name: {"min": float(frame[name].min()), "max": float(frame[name].max())}
            for name in ("Tmax_K", "Jmax_A_m2", "voltage_drop_mV", "joule_power_W", "copper_mass_kg", "energy_imbalance_percent")
        },
        "constraint_summary": {
            "feasible_cases": int(frame["constraints_passed"].sum()),
            "infeasible_cases": int((~frame["constraints_passed"]).sum()),
            "temperature_violations": int((~frame["temperature_constraint_passed"]).sum()),
            "voltage_violations": int((~frame["voltage_constraint_passed"]).sum()),
            "current_density_violations": int((~frame["current_density_constraint_passed"]).sum()),
        },
        "wall_seconds": elapsed,
        "artifacts": {
            "csv": str(csv_path.relative_to(ROOT)),
            "evaluated_csv": str(evaluated_path.relative_to(ROOT)),
            "mph": str((OUTPUT / "busbar_geometry_smoke_final.mph").relative_to(ROOT)),
            "runner": str((OUTPUT / "run_busbar_geometry_smoke.m").relative_to(ROOT)),
        },
        "scope": "One-factor low/high geometry smoke tests verify topology stability. They do not replace the 80-case multivariable design or independent holdout.",
    }
    (OUTPUT / "geometry_smoke_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    node = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    spec = json.loads((ROOT / "configs" / "busbar_eda_design_problem.json").read_text(encoding="utf-8"))
    cases = cases_from_spec(spec)
    runner = build_runner(node, cases)
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
    report = validate(cases, time.perf_counter() - started)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

