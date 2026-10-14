from __future__ import annotations

import json
from itertools import product
from pathlib import Path
from typing import Any


def load_thermal_sweep_spec(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"kind", "model_name", "physics", "inputs", "outputs", "sampling"}
    missing = required - set(data)
    if missing:
        raise ValueError(f"thermal sweep spec missing: {', '.join(sorted(missing))}")
    if data["physics"] != "heat_transfer_solid_2d":
        raise ValueError("thermal sweep currently supports heat_transfer_solid_2d only")
    return data


def thermal_sweep_rows(spec: dict[str, Any]) -> list[dict[str, float]]:
    sampling = dict(spec["sampling"])
    names = ["L_m", "W_m", "k_W_mK", "T_hot_K", "T_cold_K"]
    return [
        {name: float(value) for name, value in zip(names, values)}
        for values in product(*(sampling[name] for name in names))
    ]


def build_thermal_sweep_matlab(spec: dict[str, Any], csv_path: str | Path) -> str:
    rows = thermal_sweep_rows(spec)
    return build_thermal_samples_matlab(rows, csv_path)


def build_thermal_samples_matlab(rows: list[dict[str, float]], csv_path: str | Path) -> str:
    if not rows:
        raise ValueError("thermal sample list is empty")
    matrix = ";\n".join(" ".join(f"{row[name]:.12g}" for name in ["L_m", "W_m", "k_W_mK", "T_hot_K", "T_cold_K"]) for row in rows)
    csv = Path(csv_path).resolve().as_posix().replace("'", "''")
    return f"""% Generated local COMSOL sweep for surrogate-model training.
import com.comsol.model.*
import com.comsol.model.util.*

mphstart('localhost', 2036);
samples = [{matrix}];
results = zeros(size(samples,1), 7);
for i = 1:size(samples,1)
  L = samples(i,1); W = samples(i,2); k_mat = samples(i,3);
  T_hot = samples(i,4); T_cold = samples(i,5);
  model = ModelUtil.create(sprintf('thermal_sweep_%d', i));
  model.component.create('comp1', true);
  model.component('comp1').geom.create('geom1', 2);
  model.component('comp1').geom('geom1').create('r1', 'Rectangle');
  model.component('comp1').geom('geom1').feature('r1').set('size', {{num2str(L) num2str(W)}});
  model.component('comp1').geom('geom1').run;
  model.component('comp1').material.create('mat1', 'Common');
  model.component('comp1').material('mat1').propertyGroup('def').set('thermalconductivity', num2str(k_mat));
  model.component('comp1').physics.create('ht', 'HeatTransfer', 'geom1');
  model.component('comp1').physics('ht').selection.all;
  model.component('comp1').physics('ht').create('temp1', 'TemperatureBoundary', 1);
  model.component('comp1').physics('ht').feature('temp1').selection.set([1]);
  model.component('comp1').physics('ht').feature('temp1').set('T0', num2str(T_hot));
  model.component('comp1').physics('ht').create('temp2', 'TemperatureBoundary', 1);
  model.component('comp1').physics('ht').feature('temp2').selection.set([3]);
  model.component('comp1').physics('ht').feature('temp2').set('T0', num2str(T_cold));
  model.component('comp1').mesh.create('mesh1');
  model.component('comp1').mesh('mesh1').create('size1', 'Size');
  model.component('comp1').mesh('mesh1').feature('size1').set('custom', true);
  model.component('comp1').mesh('mesh1').feature('size1').set('hmax', num2str(min(L,W)/8));
  model.component('comp1').mesh('mesh1').create('ftri1', 'FreeTri');
  model.component('comp1').mesh('mesh1').run;
  model.component('comp1').cpl.create('maxop1', 'Maximum');
  model.component('comp1').cpl('maxop1').selection.all;
  model.component('comp1').cpl.create('aveop1', 'Average');
  model.component('comp1').cpl('aveop1').selection.all;
  model.study.create('std1');
  model.study('std1').create('stat', 'Stationary');
  model.study('std1').feature('stat').activate('ht', true);
  model.study('std1').createAutoSequences('all');
  model.study('std1').run;
  Tmax = mphglobal(model, 'maxop1(T)');
  Tavg = mphglobal(model, 'aveop1(T)');
  results(i,:) = [L W k_mat T_hot T_cold Tmax Tavg];
  ModelUtil.remove(model.tag());
end
table_out = array2table(results, 'VariableNames', {{'L_m','W_m','k_W_mK','T_hot_K','T_cold_K','Tmax_K','Tavg_K'}});
writetable(table_out, '{csv}');
fprintf('THERMAL_SWEEP_CSV={csv}\\n');
"""


def write_thermal_sweep_matlab(spec_path: str | Path, output_path: str | Path, csv_path: str | Path) -> dict[str, Any]:
    spec = load_thermal_sweep_spec(spec_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_thermal_sweep_matlab(spec, csv_path), encoding="utf-8")
    return {"spec": spec, "script_path": str(destination), "csv_path": str(Path(csv_path)), "sample_count": len(thermal_sweep_rows(spec))}
