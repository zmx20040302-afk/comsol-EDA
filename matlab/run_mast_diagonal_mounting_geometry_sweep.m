function run_mast_diagonal_mounting_geometry_sweep(model_path, output_csv, geometry_points_mm)
% Run geometry-dependent stationary structural points for the mast mounting model.
model = mphopen(model_path);
model.study('std1').feature('param').active(false);
row_count = size(geometry_points_mm, 1);
t_p_mm = zeros(row_count, 1);
t_m_mm = zeros(row_count, 1);
stiffness_ratio_1 = zeros(row_count, 1);
for index = 1:row_count
    t_p_mm(index) = geometry_points_mm(index, 1);
    t_m_mm(index) = geometry_points_mm(index, 2);
    model.param.set('t_p', sprintf('%.12g[mm]', t_p_mm(index)));
    model.param.set('t_m', sprintf('%.12g[mm]', t_m_mm(index)));
    model.component('comp1').geom('geom1').run;
    model.component('comp1').mesh('mesh1').run;
    model.study('std1').run;
    stiffness_ratio_1(index) = mphglobal(model, 'S_R');
end
result = table(t_p_mm, t_m_mm, stiffness_ratio_1);
writetable(result, output_csv);
end