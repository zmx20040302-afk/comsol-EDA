% Validate the first acoustic eigenfrequency extraction before CSV sampling.
root_dir = fileparts(fileparts(mfilename('fullpath')));
addpath('D:/COMSOL64/Multiphysics/mli');
mphstart('localhost', 2036);

source_mph = 'D:/桌面/codex/案例下载/COMSOL/房间的特征模态/eigenmodes_of_room.mph';
model = mphopen(source_mph);
model.study('std1').run;
frequencies_Hz = mphglobal(model, 'freq', 'unit', 'Hz');
positive_frequencies_Hz = sort(real(frequencies_Hz(real(frequencies_Hz) > 0)));
first_eigenfrequency_Hz = positive_frequencies_Hz(1);

output_path = fullfile(root_dir, 'generated', 'training_runs', 'eigenmodes_of_room_baseline.csv');
if ~isfolder(fileparts(output_path)); mkdir(fileparts(output_path)); end
result = table(343, first_eigenfrequency_Hz, 'VariableNames', {'sound_speed_m_s', 'first_eigenfrequency_Hz'});
writetable(result, output_path);
disp(result);
