function preflight_electric_field_concentric_cylinders(model_path, output_csv)
model = mphopen(model_path);
potential_mid_V = mphinterp(model, 'es.V', 'coord', [0.5; 0], 'unit', 'V');
electric_field_mid_V_m = mphinterp(model, 'es.normE', 'coord', [0.5; 0], 'unit', 'V/m');
result = table(potential_mid_V, electric_field_mid_V_m);
writetable(result, output_csv);
end