function run_magnetic_field_infinite_conductor_current_sweep(currents_A, output_name)
% Export COMSOL-computed magnetic flux density versus conductor current.
root_dir = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\无限导体的磁场\magnetic_field_infinite_conductor.mph';
if nargin < 1 || isempty(currents_A)
    currents_A = [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 5];
end
if nargin < 2 || isempty(output_name)
    output_name = 'magnetic_field_infinite_conductor_training.csv';
end

addpath('D:\COMSOL64\Multiphysics\mli');
mphstart('localhost', 2036);
model = mphopen(source_mph);
rows = zeros(numel(currents_A), 2);
for index = 1:numel(currents_A)
    current_A = currents_A(index);
    model.param.set('I0', sprintf('%.12g[A]', current_A));
    model.study('std1').run;
    magnetic_flux_density_T = mphinterp(model, 'mf.normB', 'coord', [0.05; 0], 'dataset', 'dset1', 'unit', 'T');
    rows(index, :) = [current_A, magnetic_flux_density_T];
    fprintf('I0=%g A, B(5 cm)=%.12g T\n', current_A, magnetic_flux_density_T);
end

output_path = fullfile(root_dir, 'generated', 'training_runs', output_name);
if ~isfolder(fileparts(output_path)); mkdir(fileparts(output_path)); end
result = array2table(rows, 'VariableNames', {'current_A', 'magnetic_flux_density_at_5cm_T'});
writetable(result, output_path);
fprintf('SWEEP_CSV=%s\n', output_path);
end
