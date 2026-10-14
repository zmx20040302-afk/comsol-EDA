% Export first acoustic eigenfrequency samples for the room-eigenmode surrogate.
root_dir = fileparts(fileparts(mfilename('fullpath')));
addpath('D:/COMSOL64/Multiphysics/mli');
mphstart('localhost', 2036);

source_mph = 'D:/桌面/codex/案例下载/COMSOL/房间的特征模态/eigenmodes_of_room.mph';
output_name = 'eigenmodes_of_room_sound_speed_training.csv';
sound_speeds_m_s = [300, 320, 343, 360, 380];
if exist('sound_speeds_override', 'var'); sound_speeds_m_s = sound_speeds_override; end
if exist('output_name_override', 'var'); output_name = output_name_override; end

model = mphopen(source_mph);
rows = zeros(numel(sound_speeds_m_s), 2);
for index = 1:numel(sound_speeds_m_s)
    sound_speed = sound_speeds_m_s(index);
    model.component('comp1').material('mat1').propertyGroup('def').set('soundspeed', {num2str(sound_speed, '%.15g')});
    model.study('std1').run;
    frequencies_Hz = mphglobal(model, 'freq', 'unit', 'Hz');
    positive_frequencies_Hz = sort(real(frequencies_Hz(real(frequencies_Hz) > 0)));
    rows(index, :) = [sound_speed, positive_frequencies_Hz(1)];
    fprintf('sound_speed=%g m/s, first_eigenfrequency=%g Hz\n', rows(index, 1), rows(index, 2));
end

output_path = fullfile(root_dir, 'generated', 'training_runs', output_name);
if ~isfolder(fileparts(output_path)); mkdir(fileparts(output_path)); end
result = array2table(rows, 'VariableNames', {'sound_speed_m_s', 'first_eigenfrequency_Hz'});
writetable(result, output_path);
disp(result);
