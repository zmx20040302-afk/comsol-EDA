"""Train a log-domain COMSOL P-N junction carrier-concentration surrogate."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression

from comsol_small_model.surrogate_model_card import register_general_surrogate, write_general_surrogate_model_card

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / 'generated/training_runs/pn_junction_carrier_training.csv'
HOLDOUT = ROOT / 'generated/training_runs/pn_junction_carrier_holdout.csv'
MODEL = ROOT / 'generated/models/pn_junction_carrier_surrogate.joblib'
INPUTS = ['bias_V']
RAW_OUTPUTS = ['electron_density_at_junction_cm3', 'hole_density_at_junction_cm3']
LOG_OUTPUTS = ['log10_electron_density_at_junction_cm3', 'log10_hole_density_at_junction_cm3']
SCOPE = '一维硅 P-N 结稳态半导体模型；Tl=300 K、Na=Nd=1e15 1/cm^3、几何、材料、网格和金属接触固定，仅改变正向偏压 0-0.5 V，输出结区 x=0 的电子和空穴浓度。'

def main() -> int:
    training, holdout = pd.read_csv(TRAINING), pd.read_csv(HOLDOUT)
    x_train = training[INPUTS].to_numpy(float)
    x_holdout = holdout[INPUTS].to_numpy(float)
    y_train = np.log10(training[RAW_OUTPUTS].to_numpy(float))
    y_holdout = holdout[RAW_OUTPUTS].to_numpy(float)
    model = Pipeline([('poly', PolynomialFeatures(degree=2)), ('linear', LinearRegression())])
    model.fit(x_train, y_train)
    predicted = 10.0 ** model.predict(x_holdout)
    errors = np.abs(predicted - y_holdout) / np.maximum(np.abs(y_holdout), 1e-30) * 100.0
    max_error, mean_error = float(errors.max()), float(errors.mean())
    passed = max_error <= 5.0
    validation = {'kind':'pn_junction_carrier_independent_comsol_validation','created_at':datetime.now(timezone.utc).isoformat(),'training_csv':str(TRAINING.resolve()),'holdout_csv':str(HOLDOUT.resolve()),'training_rows':len(training),'holdout_rows':len(holdout),'selected_model':'quadratic_regression_on_log10_carrier_densities','selection_reason':'Carrier injection varies exponentially with forward bias, so the model fits log10 concentrations and transforms predictions back to physical units.','per_output_relative_validation':{name:{'max_relative_error_percent':max_error,'mean_relative_error_percent':mean_error,'threshold_relative_error_percent':5.0,'passed':passed} for name in RAW_OUTPUTS},'passed':passed,'scope':SCOPE}
    report_path = MODEL.with_suffix('.holdout_validation.json')
    validation['path'] = str(report_path.resolve())
    report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding='utf-8')
    joblib.dump({'model':model,'model_name':'quadratic_regression_on_log10_carrier_densities','input_columns':INPUTS,'output_columns':RAW_OUTPUTS,'log_transformed_outputs':RAW_OUTPUTS,'selection_method':'independent_comsol_holdout','training_csv_path':str(TRAINING.resolve())}, MODEL)
    card = write_general_surrogate_model_card(model_name='一维 P-N 结结区载流子浓度代理模型',model_path=MODEL,training_csv=TRAINING,holdout_csv=HOLDOUT,input_columns=INPUTS,output_columns=RAW_OUTPUTS,physical_scope=SCOPE,validation=validation,output_dir=MODEL.parent)
    register_general_surrogate(model_name='一维 P-N 结结区载流子浓度代理模型',model_path=MODEL,card=card,validation=validation,registry_path=ROOT / 'generated/models/surrogate_registry.json')
    print(json.dumps(validation, ensure_ascii=False))
    return 0 if passed else 1

if __name__ == '__main__':
    raise SystemExit(main())
