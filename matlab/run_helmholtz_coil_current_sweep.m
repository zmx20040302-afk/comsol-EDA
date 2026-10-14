function run_helmholtz_coil_current_sweep(currents_mA, output_name)
% Export COMSOL-computed signed center field versus equal coil current.
root_dir = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\亥姆霍兹线圈的磁场\helmholtz_coil.mph';
if nargin < 1 || isempty(currents_mA)
    currents_mA = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6];
end
if nargin < 2 || isempty(output_name)
    output_name = 'helmholtz_coil_training.csv';
end

addpath('D:\COMSOL64\Multiphysics\mli');
mphstart('localhost', 2036);
model = mphopen(source_mph);
model.study('std1').feature('stat2').active(false);
rows = zeros(numel(currents_mA), 2);
for index = 1:numel(currents_mA)
    current_mA = currents_mA(index);
    model.param.set('I0', sprintf('%.12g[mA]', current_mA));
    model.study('std1').run;
    center_By_T = mphinterp(model, 'mf.By', 'coord', [0; 0; 0], 'dataset', 'dset1', 'unit', 'T');
    rows(index, :) = [current_mA, center_By_T];
    fprintf('I0=%g mA, By(center)=%.12g T\n', current_mA, center_By_T);
end

output_path = fullfile(root_dir, 'generated', 'training_runs', output_name);
if ~isfolder(fileparts(output_path)); mkdir(fileparts(output_path)); end
result = array2table(rows, 'VariableNames', {'coil_current_mA', 'center_By_T'});
writetable(result, output_path);
fprintf('SWEEP_CSV=%s\n', output_path);
end
