function run_simple_resistor_conductivity_sweep(model_path, output_csv, conductivity_values_S_m)
% Sweep isotropic conductivity with fixed geometry, 1 A terminal, and ground.
model = mphopen(model_path);
row_count = numel(conductivity_values_S_m);
conductivity_S_m = nan(row_count, 1);
resistance_ohm = nan(row_count, 1);
for index = 1:row_count
    conductivity_S_m(index) = conductivity_values_S_m(index);
    sigma = sprintf('%.12g[S/m]', conductivity_S_m(index));
    model.component('comp1').material('mat1').propertyGroup('def').set('electricconductivity', ...
        {sigma '0' '0' '0' sigma '0' '0' '0' sigma});
    model.study('std1').run;
    resistance_ohm(index) = mphglobal(model, 'ec.R11', 'unit', 'ohm');
    completed = table(conductivity_S_m(1:index), resistance_ohm(1:index), ...
        'VariableNames', {'conductivity_S_m', 'resistance_ohm'});
    writetable(completed, output_csv);
    fprintf('simple_resistor completed %d/%d at sigma=%.12g S/m\n', index, row_count, conductivity_S_m(index));
end
end
