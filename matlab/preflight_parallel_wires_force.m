function preflight_parallel_wires_force()
% Verify force extraction for the parallel-current-carrying-wires case.
project_root = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\平行载流导线上的电磁力\parallel_wires.mph';
output_csv = fullfile(project_root, 'generated', 'training_runs', 'parallel_wires_force_preflight.csv');

addpath('D:\COMSOL64\Multiphysics\mli');
mphstart('localhost', 2036);
model = mphopen(source_mph);
current_A = 1.0;
model.param.set('I0', sprintf('%.12g[A]', current_A));
model.study('std1').run;
force_x_wire2_N = mphglobal(model, 'mf.Forcex_wire2', 'dataset', 'dset1', 'solnum', 'end', 'unit', 'N');

result = table(current_A, force_x_wire2_N(end), 'VariableNames', {'current_A', 'force_x_wire2_N'});
writetable(result, output_csv);
fprintf('PREFLIGHT_CSV=%s\n', output_csv);
fprintf('FORCE_X_WIRE2_N=%.12g\n', force_x_wire2_N(end));
end
