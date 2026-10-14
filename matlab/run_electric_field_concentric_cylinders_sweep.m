function run_electric_field_concentric_cylinders_sweep(model_path, output_csv, voltage_values_V)
% Run stationary electrostatic points and checkpoint each completed result.
model = mphopen(model_path);
row_count = numel(voltage_values_V);
voltage_V = nan(row_count, 1);
potential_mid_V = nan(row_count, 1);
electric_field_mid_V_m = nan(row_count, 1);
for index = 1:row_count
    voltage_V(index) = voltage_values_V(index);
    model.param.set('V0', sprintf('%.12g[V]', voltage_V(index)));
    model.study('std1').run;
    potential_mid_V(index) = mphinterp(model, 'V', 'coord', 0.5, 'unit', 'V');
    dr = 1e-4;
    potential_plus_V = mphinterp(model, 'V', 'coord', 0.5 + dr, 'unit', 'V');
    potential_minus_V = mphinterp(model, 'V', 'coord', 0.5 - dr, 'unit', 'V');
    electric_field_mid_V_m(index) = -(potential_plus_V - potential_minus_V) / (2 * dr);
    completed = table(voltage_V(1:index), potential_mid_V(1:index), electric_field_mid_V_m(1:index), ...
        'VariableNames', {'voltage_V', 'potential_mid_V', 'electric_field_mid_V_m'});
    writetable(completed, output_csv);
    fprintf('electric_field_concentric_cylinders completed %d/%d at V0=%.12g V\n', index, row_count, voltage_V(index));
end
end
