function preflight_fresnel_equations_rf()
% Validate TE/TM reflectance extraction from the original COMSOL model.
project_root = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\菲涅尔方程 (RF)\fresnel_equations.mph';
output_csv = fullfile(project_root, 'generated', 'training_runs', 'fresnel_equations_rf_preflight.csv');

addpath('D:\COMSOL64\Multiphysics\mli');
mphstart('localhost', 2036);
model = mphopen(source_mph);

angle_deg = 45;
angle_expr = sprintf('%.12g[deg]', angle_deg);

model.study('std1').feature('param').set('plistarr', {angle_expr});
model.study('std1').run;
reflectance_te = mphglobal(model, 'abs(emw.S11)^2', 'dataset', 'dset1', 'solnum', 'end');

model.study('std2').feature('param').set('plistarr', {angle_expr});
model.study('std2').run;
reflectance_tm = mphglobal(model, 'abs(emw2.S11)^2', 'dataset', 'dset3', 'solnum', 'end');

result = table(angle_deg, reflectance_te(end), reflectance_tm(end), ...
    'VariableNames', {'incident_angle_deg', 'TE_reflectance', 'TM_reflectance'});
writetable(result, output_csv);
fprintf('PREFLIGHT_CSV=%s\n', output_csv);
fprintf('TE_REFLECTANCE=%.12g\n', reflectance_te(end));
fprintf('TM_REFLECTANCE=%.12g\n', reflectance_tm(end));
end
