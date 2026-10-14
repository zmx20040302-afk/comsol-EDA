from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "p3" / "current_drive_baseline"
SOURCE_MPH = ROOT / "generated" / "benchmarks" / "busbar_joule_heat" / "builders" / "busbar_joule_heat_baseline.mph"
SPEC_PATH = ROOT / "configs" / "busbar_eda_design_problem.json"


def q(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_runner(node: dict, spec: dict) -> Path:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    baseline = spec["baseline"]
    nominal = spec["drive_definition"]["nominal_current_A"]
    runner = OUTPUT / "run_busbar_current_drive_baseline.m"
    csv_path = OUTPUT / "busbar_current_drive_baseline.csv"
    mph_path = OUTPUT / "busbar_current_drive_baseline.mph"
    png_path = OUTPUT / "busbar_current_drive_baseline.png"
    error_path = OUTPUT / "busbar_current_drive_baseline.error.txt"
    script = f"""addpath('{str(node['livelink_matlab_path']).replace(chr(92), '/')}');
mphstart('{node.get('comsol_server_host', 'localhost')}', {int(node.get('comsol_server_port', 2036))});
model = mphopen('{q(SOURCE_MPH)}');
output_csv = '{q(csv_path)}';
output_mph = '{q(mph_path)}';
output_png = '{q(png_path)}';
error_path = '{q(error_path)}';
if isfile(error_path), delete(error_path); end
total_timer = tic;
try
  old_terminal = mphgetselection(model.component('comp1').physics('ec').feature('pot1'));
  model.component('comp1').physics('ec').feature.remove('pot1');
  model.param.set('I_load', '{nominal:.12g}[A]');
  model.param.descr('I_load', 'Fixed terminal current for comparable geometry optimization');
  model.component('comp1').physics('ec').create('term1', 'Terminal', 2);
  model.component('comp1').physics('ec').feature('term1').selection.set(old_terminal.entities);
  model.component('comp1').physics('ec').feature('term1').set('I0', 'I_load');
  solve_timer = tic;
  model.study('std1').run;
  solve_seconds = toc(solve_timer);
  terminal_selection = mphgetselection(model.component('comp1').physics('ec').feature('term1'));
  convection_selection = mphgetselection(model.component('comp1').physics('ht').feature('hf1'));
  tmax_k = mphmax(model, 'T', 3);
  tavg_k = mphmean(model, 'T', 3);
  jmax_a_m2 = mphmax(model, 'ec.normJ', 3);
  terminal_current_a = abs(mphint2(model, 'ec.nJ', 2, 'selection', terminal_selection.entities'));
  voltage_drop_v = abs(mphmean(model, 'V', 2, 'selection', terminal_selection.entities'));
  voltage_drop_mv = voltage_drop_v*1000;
  joule_power_w = mphint2(model, 'ec.Qh', 3);
  convection_power_w = abs(mphint2(model, 'ht.nteflux', 2, 'selection', convection_selection.entities'));
  energy_imbalance_percent = abs(joule_power_w-convection_power_w)/joule_power_w*100;
  copper_volume_m3 = mphint2(model, '1', 3, 'selection', 1);
  copper_mass_kg = copper_volume_m3*8960;
  solver_status = string('solved');
  result = table(tmax_k, tavg_k, jmax_a_m2, terminal_current_a, voltage_drop_mv, joule_power_w, convection_power_w, energy_imbalance_percent, copper_volume_m3, copper_mass_kg, solve_seconds, solver_status, ...
    'VariableNames', {{'Tmax_K','Tavg_K','Jmax_A_m2','terminal_current_A','voltage_drop_mV','joule_power_W','convection_power_W','energy_imbalance_percent','copper_volume_m3','copper_mass_kg','solve_seconds','solver_status'}});
  writetable(result, output_csv);
  mphsave(model, output_mph);
  try
    preview = figure('Visible', 'off');
    mphplot(model, 'pg3');
    exportgraphics(preview, output_png, 'Resolution', 150);
    close(preview);
  catch previewError
    fprintf('P3_PREVIEW_WARNING %s\\n', previewError.message);
  end
  fprintf('P3_CURRENT_DRIVE_SUCCESS current_A=%.9g voltage_mV=%.9g Tmax_K=%.9g power_W=%.9g solve_seconds=%.6f total_seconds=%.6f\\n', terminal_current_a, voltage_drop_mv, tmax_k, joule_power_w, solve_seconds, toc(total_timer));
catch errorInfo
  error_file = fopen(error_path, 'w');
  fprintf(error_file, '%s\\n', getReport(errorInfo, 'extended', 'hyperlinks', 'off'));
  fclose(error_file);
  rethrow(errorInfo);
end
"""
    runner.write_text(script, encoding="utf-8")
    return runner


def validate_outputs(spec: dict, elapsed: float) -> dict:
    csv_path = OUTPUT / "busbar_current_drive_baseline.csv"
    mph_path = OUTPUT / "busbar_current_drive_baseline.mph"
    png_path = OUTPUT / "busbar_current_drive_baseline.png"
    if not csv_path.is_file():
        error_path = OUTPUT / "busbar_current_drive_baseline.error.txt"
        detail = error_path.read_text(encoding="utf-8", errors="replace") if error_path.is_file() else "missing CSV"
        raise RuntimeError(detail)
    row = pd.read_csv(csv_path).iloc[0].to_dict()
    baseline = spec["baseline"]
    checks = {
        "terminal_current_within_1_percent": abs(float(row["terminal_current_A"]) - 160.0) <= 1.6,
        "baseline_equivalent_voltage_within_1_mV": abs(float(row["voltage_drop_mV"]) - float(baseline["Vtot_mV"]) * 160.0 / float(baseline["terminal_current_A"])) <= 1.0,
        "temperature_within_2_K_of_voltage_baseline": abs(float(row["Tmax_K"]) - float(baseline["Tmax_K"])) <= 2.0,
        "energy_imbalance_below_0_1_percent": float(row["energy_imbalance_percent"]) <= 0.1,
        "temperature_below_provisional_limit": float(row["Tmax_K"]) <= 373.15,
        "mph_created": mph_path.is_file() and mph_path.stat().st_size > 0,
    }
    artifacts = {}
    for name, path in {"runner": OUTPUT / "run_busbar_current_drive_baseline.m", "csv": csv_path, "mph": mph_path, "preview_png": png_path}.items():
        artifacts[name] = {
            "path": str(path.relative_to(ROOT)),
            "exists": path.is_file(),
            "size_bytes": path.stat().st_size if path.is_file() else 0,
            "sha256": sha256(path) if path.is_file() else "",
        }
    report = {
        "schema": "comsol-p3-current-drive-baseline",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_mph": str(SOURCE_MPH.relative_to(ROOT)),
        "drive_mode": "fixed_terminal_current",
        "nominal_current_A": 160.0,
        "measured": row,
        "checks": checks,
        "passed": all(checks.values()),
        "wall_seconds": elapsed,
        "artifacts": artifacts,
        "scope": "This verifies current-drive migration at the baseline geometry. It does not yet verify all 80 geometry candidates.",
    }
    (OUTPUT / "current_drive_baseline_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    node = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    runner = build_runner(node, spec)
    matlab = Path(node["matlab_executable"])
    if not matlab.is_file():
        raise FileNotFoundError(f"MATLAB executable not found: {matlab}")
    started = time.perf_counter()
    result = subprocess.run(
        [str(matlab), "-batch", f"run('{q(runner)}')"],
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
    report = validate_outputs(spec, time.perf_counter() - started)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

