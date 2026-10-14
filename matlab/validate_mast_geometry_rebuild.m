function validate_mast_geometry_rebuild(model_path, output_csv, t_p_mm, t_m_mm)
% Validate one geometry-dependent stationary point before any batch sweep.
model = mphopen(model_path);
model.param.set('t_p', sprintf('%.12g[mm]', t_p_mm));
model.param.set('t_m', sprintf('%.12g[mm]', t_m_mm));
model.study('std1').feature('param').active(false);
model.component('comp1').geom('geom1').run;
model.component('comp1').mesh('mesh1').run;
model.study('std1').run;
stiffness_ratio_1 = mphglobal(model, 'S_R');
result = table(t_p_mm, t_m_mm, stiffness_ratio_1);
writetable(result, output_csv);
end