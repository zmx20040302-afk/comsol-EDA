function run_thermoelectric_generator_temperature_sweep(temperatures_degC, output_name)
% Export COMSOL coupled thermoelectric open-circuit voltage versus hot temperature.
root_dir = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\热电发电机\thermoelectric_generator.mph';
if nargin < 1 || isempty(temperatures_degC)
    temperatures_degC = [100, 120, 140, 160, 180, 200];
end
if nargin < 2 || isempty(output_name)
    output_name = 'thermoelectric_generator_training.csv';
end

addpath('D:\COMSOL64\Multiphysics\mli');
mphstart('localhost', 2036);
model = mphopen(source_mph);
rows = zeros(numel(temperatures_degC), 2);
for index = 1:numel(temperatures_degC)
    hot_temperature_degC = temperatures_degC(index);
    model.param.set('T0', sprintf('%.12g[degC]', hot_temperature_degC));
    model.study('std1').run;
    open_circuit_voltage_V = mphglobal(model, 'ec.fp1.V0', 'dataset', 'dset1', 'solnum', 'end', 'unit', 'V');
    rows(index, :) = [hot_temperature_degC, open_circuit_voltage_V(end)];
    fprintf('T0=%g degC, V_oc=%.12g V\n', hot_temperature_degC, open_circuit_voltage_V(end));
end

output_path = fullfile(root_dir, 'generated', 'training_runs', output_name);
if ~isfolder(fileparts(output_path)); mkdir(fileparts(output_path)); end
result = array2table(rows, 'VariableNames', {'hot_temperature_degC', 'open_circuit_voltage_V'});
writetable(result, output_path);
fprintf('SWEEP_CSV=%s\n', output_path);
end
