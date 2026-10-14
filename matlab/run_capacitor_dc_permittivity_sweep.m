function run_capacitor_dc_permittivity_sweep(model_path, output_csv, relative_permittivity_values)
% Sweep the quartz relative permittivity while keeping geometry and terminals fixed.
model = mphopen(model_path);
row_count = numel(relative_permittivity_values);
relative_permittivity = nan(row_count, 1);
capacitance_F = nan(row_count, 1);
for index = 1:row_count
    relative_permittivity(index) = relative_permittivity_values(index);
    epsilon_r = sprintf('%.12g', relative_permittivity(index));
    model.component('comp1').material('mat1').propertyGroup('def').set('relpermittivity', ...
        {epsilon_r '0' '0' '0' epsilon_r '0' '0' '0' epsilon_r});
    model.study('std1').run;
    capacitance_F(index) = mphglobal(model, 'es.C11', 'unit', 'F');
    completed = table(relative_permittivity(1:index), capacitance_F(1:index), ...
        'VariableNames', {'relative_permittivity', 'capacitance_F'});
    writetable(completed, output_csv);
    fprintf('capacitor_dc completed %d/%d at epsilon_r=%.12g\n', index, row_count, relative_permittivity(index));
end
end
