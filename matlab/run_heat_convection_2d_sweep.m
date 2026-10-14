function run_heat_convection_2d_sweep(model_path, output_csv, h_values_W_m2_K)
% Run independent 2D conduction/convection stationary points with CSV checkpoints.
model = mphopen(model_path);
row_count = numel(h_values_W_m2_K);
convection_coefficient_W_m2_K = nan(row_count, 1);
temperature_at_0p6_0p2_K = nan(row_count, 1);
maximum_temperature_K = nan(row_count, 1);
for index = 1:row_count
    convection_coefficient_W_m2_K(index) = h_values_W_m2_K(index);
    model.component('comp1').physics('ht').feature('hf1').set('h', convection_coefficient_W_m2_K(index));
    model.study('std1').run;
    temperature_at_0p6_0p2_K(index) = mphinterp(model, 'T', 'coord', [0.6; 0.2], 'unit', 'K');
    maximum_temperature_K(index) = mphmax(model, 'T', 'surface', 'unit', 'K');
    completed = table(convection_coefficient_W_m2_K(1:index), temperature_at_0p6_0p2_K(1:index), maximum_temperature_K(1:index), 'VariableNames', {'convection_coefficient_W_m2_K', 'temperature_at_0p6_0p2_K', 'maximum_temperature_K'});
    writetable(completed, output_csv);
    fprintf('heat_convection_2d completed %d/%d at h=%.12g W/(m^2*K)\n', index, row_count, convection_coefficient_W_m2_K(index));
end
end