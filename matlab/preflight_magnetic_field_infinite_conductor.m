function preflight_magnetic_field_infinite_conductor()
% Verify COMSOL magnetic-flux-density extraction for the infinite-conductor case.
project_root = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\无限导体的磁场\magnetic_field_infinite_conductor.mph';
output_csv = fullfile(project_root, 'generated', 'training_runs', 'magnetic_field_infinite_conductor_preflight.csv');

addpath('D:\COMSOL64\Multiphysics\mli');
mphstart('localhost', 2036);
model = mphopen(source_mph);
current_A = 1.0;
model.param.set('I0', sprintf('%.12g[A]', current_A));
model.study('std1').run;
magnetic_flux_density_T = mphinterp(model, 'mf.normB', 'coord', [0.05; 0], 'dataset', 'dset1', 'unit', 'T');

result = table(current_A, magnetic_flux_density_T, 'VariableNames', {'current_A', 'magnetic_flux_density_at_5cm_T'});
writetable(result, output_csv);
fprintf('PREFLIGHT_CSV=%s\n', output_csv);
fprintf('B_5CM_T=%.12g\n', magnetic_flux_density_T);
end
