function preflight_mast_diagonal_mounting_sensitivity(model_path, output_csv)
% Read the saved stationary structural solution and export the dimensionless stiffness ratio.
model = mphopen(model_path);
stiffness_ratio_1 = mphglobal(model, 'S_R');
result = table(stiffness_ratio_1);
writetable(result, output_csv);
end