function run_heat_radiation_1d_emissivity_sweep(model_path, output_csv, emissivity_values)
% Sweep the radiating-end emissivity for the fixed one-dimensional model.
model = mphopen(model_path);
row_count = numel(emissivity_values);
emissivity = nan(row_count, 1);
radiating_end_temperature_K = nan(row_count, 1);
for index = 1:row_count
    emissivity(index) = emissivity_values(index);
    model.component('comp1').physics('ht').feature('sar1').set('epsilon_rad', emissivity(index));
    model.study('std1').run;
    radiating_end_temperature_K(index) = mphinterp(model, 'T', 'coord', 0.1, 'unit', 'K');
    completed = table(emissivity(1:index), radiating_end_temperature_K(1:index), ...
        'VariableNames', {'emissivity', 'radiating_end_temperature_K'});
    writetable(completed, output_csv);
    fprintf('heat_radiation_1d completed %d/%d at emissivity=%.12g\n', index, row_count, emissivity(index));
end
end
