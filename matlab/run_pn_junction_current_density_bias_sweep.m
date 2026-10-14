function run_pn_junction_current_density_bias_sweep(biases_V, output_name)
% Export verified P-N junction current density from the COMSOL Semiconductor interface.
if nargin < 1 || isempty(biases_V)
    biases_V = [0.05 0.1 0.2 0.3 0.4 0.5];
end
if nargin < 2 || isempty(output_name)
    output_name = 'pn_junction_current_density_training.csv';
end
project_root = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\P-N 结 - 一维\pn_junction_1d.mph';
output_csv = fullfile(project_root, 'generated', 'training_runs', output_name);

addpath('D:\COMSOL64\Multiphysics\mli');
try
    mphstart('localhost', 2036);
catch exception
    if ~contains(exception.message, 'Already connected')
        rethrow(exception);
    end
end
model = mphopen(source_mph);
rows = zeros(numel(biases_V), 2);
for index = 1:numel(biases_V)
    bias_V = biases_V(index);
    model.param.set('bias', sprintf('%.12g[V]', bias_V));
    model.param.set('sweep', '1');
    model.study('std1').feature('stat').set('plistarr', {sprintf('%.12g', bias_V), '1'});
    model.study('std1').run;
    current_density_A_m2 = mphinterp(model, 'semi.JX', 'coord', 2.5e-6, ...
        'dataset', 'dset1', 'solnum', 'end', 'unit', 'A/m^2');
    rows(index, :) = [bias_V, current_density_A_m2(end)];
    fprintf('BIAS=%.6g V  JX=%.12g A/m^2\n', bias_V, current_density_A_m2(end));
end
result = array2table(rows, 'VariableNames', {'bias_V', 'current_density_at_x_2_5um_A_m2'});
writetable(result, output_csv);
fprintf('CURRENT_DENSITY_CSV=%s\n', output_csv);
end
