function run_parallel_wires_force_current_sweep(currents_A, output_name)
% Export COMSOL-computed force on wire 2 versus common conductor current.
root_dir = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\平行载流导线上的电磁力\parallel_wires.mph';
if nargin < 1 || isempty(currents_A)
    currents_A = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3];
end
if nargin < 2 || isempty(output_name)
    output_name = 'parallel_wires_force_training.csv';
end

addpath('D:\COMSOL64\Multiphysics\mli');
mphstart('localhost', 2036);
model = mphopen(source_mph);
rows = zeros(numel(currents_A), 2);
for index = 1:numel(currents_A)
    current_A = currents_A(index);
    model.param.set('I0', sprintf('%.12g[A]', current_A));
    model.study('std1').run;
    force_x_wire2_N = mphglobal(model, 'mf.Forcex_wire2', 'dataset', 'dset1', 'solnum', 'end', 'unit', 'N');
    rows(index, :) = [current_A, force_x_wire2_N(end)];
    fprintf('I0=%g A, F_x(wire2)=%.12g N\n', current_A, force_x_wire2_N(end));
end

output_path = fullfile(root_dir, 'generated', 'training_runs', output_name);
if ~isfolder(fileparts(output_path)); mkdir(fileparts(output_path)); end
result = array2table(rows, 'VariableNames', {'current_A', 'force_x_wire2_N'});
writetable(result, output_path);
fprintf('SWEEP_CSV=%s\n', output_path);
end
