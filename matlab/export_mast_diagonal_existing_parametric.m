function export_mast_diagonal_existing_parametric(model_path, output_csv)
% Export the source model's saved t_p/t_m parametric solution without re-solving it.
model = mphopen(model_path);
t_p_m = mphglobal(model, 't_p', 'dataset', 'dset2');
t_m_m = mphglobal(model, 't_m', 'dataset', 'dset2');
stiffness_ratio_1 = mphglobal(model, 'S_R', 'dataset', 'dset2');
result = table(t_p_m(:), t_m_m(:), stiffness_ratio_1(:));
writetable(result, output_csv);
end