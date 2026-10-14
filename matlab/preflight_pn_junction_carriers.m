function preflight_pn_junction_carriers()
% Verify carrier-concentration outputs at the P-N junction under forward bias.
project_root = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\P-N 结 - 一维\pn_junction_1d.mph';
output_csv = fullfile(project_root, 'generated', 'training_runs', 'pn_junction_carriers_preflight.csv');

addpath('D:\COMSOL64\Multiphysics\mli');
mphstart('localhost', 2036);
model = mphopen(source_mph);
bias_V = 0.5;
model.param.set('bias', sprintf('%.12g[V]', bias_V));
model.param.set('sweep', '1');
model.study('std1').feature('stat').set('plistarr', {sprintf('%.12g', bias_V), '1'});
model.study('std1').run;
electron_density_cm3 = mphinterp(model, 'semi.N', 'coord', 0, 'dataset', 'dset1', 'solnum', 'end', 'unit', '1/cm^3');
hole_density_cm3 = mphinterp(model, 'semi.P', 'coord', 0, 'dataset', 'dset1', 'solnum', 'end', 'unit', '1/cm^3');

result = table(bias_V, electron_density_cm3(end), hole_density_cm3(end), 'VariableNames', {'bias_V', 'electron_density_at_junction_cm3', 'hole_density_at_junction_cm3'});
writetable(result, output_csv);
fprintf('PREFLIGHT_CSV=%s\n', output_csv);
fprintf('N_JUNCTION=%.12g  P_JUNCTION=%.12g\n', electron_density_cm3(end), hole_density_cm3(end));
end
