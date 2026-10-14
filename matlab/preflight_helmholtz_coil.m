function preflight_helmholtz_coil()
% Validate center-field extraction from the full Magnetic Fields study.
project_root = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\亥姆霍兹线圈的磁场\helmholtz_coil.mph';
output_csv = fullfile(project_root, 'generated', 'training_runs', 'helmholtz_coil_preflight.csv');

addpath('D:\COMSOL64\Multiphysics\mli');
mphstart('localhost', 2036);
model = mphopen(source_mph);
current_mA = 0.25;
model.param.set('I0', sprintf('%.12g[mA]', current_mA));
model.study('std1').feature('stat2').active(false);
model.study('std1').run;
magnetic_field_y_T = mphinterp(model, 'mf.By', 'coord', [0; 0; 0], 'dataset', 'dset1', 'unit', 'T');

result = table(current_mA, magnetic_field_y_T, 'VariableNames', {'coil_current_mA', 'center_By_T'});
writetable(result, output_csv);
fprintf('PREFLIGHT_CSV=%s\n', output_csv);
fprintf('CENTER_BY_T=%.12g\n', magnetic_field_y_T);
end
