function run_micromixer_velocity_sweep(model_path, output_csv, velocity_mm_s)
% Run independent stationary micromixer points and checkpoint each completed row.
model = mphopen(model_path);
row_count = numel(velocity_mm_s);
mean_velocity_mm_s = nan(row_count, 1);
relative_concentration_variance_outlet = nan(row_count, 1);
for index = 1:row_count
    mean_velocity_mm_s(index) = velocity_mm_s(index);
    model.param.set('U_mean', sprintf('%.12g[mm/s]', mean_velocity_mm_s(index)));
    model.study('std1').run;
    relative_concentration_variance_outlet(index) = mphglobal(model, 'S_outlet', 'unit', '1');
    completed = table(mean_velocity_mm_s(1:index), relative_concentration_variance_outlet(1:index));
    writetable(completed, output_csv);
    fprintf('micromixer completed %d/%d at U_mean=%.12g mm/s, S_outlet=%.12g\n', index, row_count, mean_velocity_mm_s(index), relative_concentration_variance_outlet(index));
end
end