function preflight_micromixer(model_path, output_csv)
% Read the saved micromixer solution and export the reusable mixing metric.
model = mphopen(model_path);
mean_velocity_m_s = mphglobal(model, 'U_mean', 'unit', 'm/s');
relative_concentration_variance_outlet = mphglobal(model, 'S_outlet', 'unit', '1');
result = table(mean_velocity_m_s, relative_concentration_variance_outlet);
writetable(result, output_csv);
end
