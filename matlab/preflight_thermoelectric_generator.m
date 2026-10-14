function preflight_thermoelectric_generator()
% Verify thermoelectric voltage extraction from the coupled heat/electric model.
project_root = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\热电发电机\thermoelectric_generator.mph';
output_csv = fullfile(project_root, 'generated', 'training_runs', 'thermoelectric_generator_preflight.csv');

addpath('D:\COMSOL64\Multiphysics\mli');
mphstart('localhost', 2036);
model = mphopen(source_mph);
hot_temperature_degC = 100;
model.param.set('T0', sprintf('%.12g[degC]', hot_temperature_degC));
model.study('std1').run;
open_circuit_voltage_V = mphglobal(model, 'ec.fp1.V0', 'dataset', 'dset1', 'solnum', 'end', 'unit', 'V');

result = table(hot_temperature_degC, open_circuit_voltage_V(end), 'VariableNames', {'hot_temperature_degC', 'open_circuit_voltage_V'});
writetable(result, output_csv);
fprintf('PREFLIGHT_CSV=%s\n', output_csv);
fprintf('OPEN_CIRCUIT_VOLTAGE_V=%.12g\n', open_circuit_voltage_V(end));
end
