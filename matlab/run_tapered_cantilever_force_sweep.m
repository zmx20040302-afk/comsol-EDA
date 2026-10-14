function run_tapered_cantilever_force_sweep(model_path, output_csv, force_values_N_m)
% Sweep the boundary-force load case while retaining the original two-load-case study.
model = mphopen(model_path);
row_count = numel(force_values_N_m);
boundary_force_N_m = nan(row_count, 1);
force_case_tip_displacement_m = nan(row_count, 1);
for index = 1:row_count
    boundary_force_N_m(index) = force_values_N_m(index);
    force_x = sprintf('%.12g[N/m]', boundary_force_N_m(index));
    model.component('comp1').physics('solid').feature('bndl1').set('forceReferenceLength', {force_x; '0'; '0'});
    model.study('std1').run;
    force_case_tip_displacement_m(index) = mphinterp(model, 'sqrt(u^2+v^2)', ...
        'coord', [4; 2], 'solnum', 2, 'unit', 'm');
    completed = table(boundary_force_N_m(1:index), force_case_tip_displacement_m(1:index), ...
        'VariableNames', {'boundary_force_N_m', 'force_case_tip_displacement_m'});
    writetable(completed, output_csv);
    fprintf('tapered_cantilever completed %d/%d at force=%.12g N/m\n', index, row_count, boundary_force_N_m(index));
end
end
