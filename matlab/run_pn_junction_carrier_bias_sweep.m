function run_pn_junction_carrier_bias_sweep(biases_V, output_name)
% Export COMSOL junction carrier concentrations versus forward bias.
root_dir = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\P-N 结 - 一维\pn_junction_1d.mph';
if nargin < 1 || isempty(biases_V)
    biases_V = [0, 0.1, 0.2, 0.3, 0.4, 0.5];
end
if nargin < 2 || isempty(output_name)
    output_name = 'pn_junction_carrier_training.csv';
end

addpath('D:\COMSOL64\Multiphysics\mli');
mphstart('localhost', 2036);
model = mphopen(source_mph);
rows = zeros(numel(biases_V), 3);
for index = 1:numel(biases_V)
    bias_V = biases_V(index);
    model.param.set('bias', sprintf('%.12g[V]', bias_V));
    model.param.set('sweep', '1');
    model.study('std1').feature('stat').set('plistarr', {sprintf('%.12g', bias_V), '1'});
    model.study('std1').run;
    electron_density_cm3 = mphinterp(model, 'semi.N', 'coord', 0, 'dataset', 'dset1', 'solnum', 'end', 'unit', '1/cm^3');
    hole_density_cm3 = mphinterp(model, 'semi.P', 'coord', 0, 'dataset', 'dset1', 'solnum', 'end', 'unit', '1/cm^3');
    rows(index, :) = [bias_V, electron_density_cm3(end), hole_density_cm3(end)];
    fprintf('bias=%g V, N=%.12g, P=%.12g 1/cm^3\n', bias_V, electron_density_cm3(end), hole_density_cm3(end));
end

output_path = fullfile(root_dir, 'generated', 'training_runs', output_name);
if ~isfolder(fileparts(output_path)); mkdir(fileparts(output_path)); end
result = array2table(rows, 'VariableNames', {'bias_V', 'electron_density_at_junction_cm3', 'hole_density_at_junction_cm3'});
writetable(result, output_path);
fprintf('SWEEP_CSV=%s\n', output_path);
end
