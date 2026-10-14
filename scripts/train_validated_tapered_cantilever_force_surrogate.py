"""Train a declared-scope linear load-to-displacement cantilever surrogate."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from comsol_small_model.surrogate_model_card import register_general_surrogate, write_general_surrogate_model_card

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "generated/training_runs/tapered_cantilever_force_training.csv"
HOLDOUT = ROOT / "generated/training_runs/tapered_cantilever_force_holdout.csv"
MODEL = ROOT / "generated/models/tapered_cantilever_force_surrogate.joblib"
INPUTS, OUTPUTS = ["boundary_force_N_m"], ["force_case_tip_displacement_m"]
SCOPE = "二维锥形悬臂梁小变形线弹性静力学；固定几何、E=210 GPa、nu=0.3、重力工况、约束和网格，仅改变边界力工况 5e6-1.5e7 N/m。"

def main() -> int:
    training, holdout = pd.read_csv(TRAINING), pd.read_csv(HOLDOUT)
    model = LinearRegression().fit(training[INPUTS].to_numpy(float), training[OUTPUTS].to_numpy(float))
    actual = holdout[OUTPUTS].to_numpy(float); predicted = model.predict(holdout[INPUTS].to_numpy(float))
    error = np.abs(predicted - actual) / np.maximum(np.abs(actual), 1e-30) * 100.0
    max_error = float(error.max()); passed = max_error <= 1.0
    validation = {"kind":"tapered_cantilever_force_independent_comsol_validation","created_at":datetime.now(timezone.utc).isoformat(),"training_csv":str(TRAINING.resolve()),"holdout_csv":str(HOLDOUT.resolve()),"training_rows":len(training),"holdout_rows":len(holdout),"selected_model":"linear_regression","selection_reason":"Small-deformation linear elastic response gives displacement proportional to applied load.","per_output_relative_validation":{OUTPUTS[0]:{"max_relative_error_percent":max_error,"mean_relative_error_percent":float(error.mean()),"threshold_relative_error_percent":1.0,"passed":passed}},"passed":passed,"scope":SCOPE}
    report_path=MODEL.with_suffix(".holdout_validation.json"); validation["path"]=str(report_path.resolve()); report_path.write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding="utf-8")
    joblib.dump({"model":model,"model_name":"linear_regression","input_columns":INPUTS,"output_columns":OUTPUTS,"selection_method":"physics_consistent_linear_with_independent_comsol_holdout","training_csv_path":str(TRAINING.resolve()),"holdout_csv_path":str(HOLDOUT.resolve())},MODEL)
    card=write_general_surrogate_model_card(model_name="锥形悬臂梁边界力位移代理模型",model_path=MODEL,training_csv=TRAINING,holdout_csv=HOLDOUT,input_columns=INPUTS,output_columns=OUTPUTS,physical_scope=SCOPE,validation=validation,output_dir=MODEL.parent)
    registry=register_general_surrogate(model_name="锥形悬臂梁边界力位移代理模型",model_path=MODEL,card=card,validation=validation,registry_path=ROOT/"generated/models/surrogate_registry.json")
    print(json.dumps({"validation":validation,"registry":registry},ensure_ascii=False)); return 0 if passed else 1
if __name__ == "__main__": raise SystemExit(main())
