function preflight_heat_convection_2d(model_path, output_csv)
% Read saved 2D conduction/convection solution in SI units.
model = mphopen(model_path);
temperature_at_0p6_0p2_K = mphinterp(model, 'T', 'coord', [0.6; 0.2], 'unit', 'K');
maximum_temperature_K = mphmax(model, 'T', 'surface', 'unit', 'K');
result = table(temperature_at_0p6_0p2_K, maximum_temperature_K);
writetable(result, output_csv);
end