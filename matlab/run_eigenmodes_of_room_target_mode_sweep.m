% Track one acoustic eigenmode consistently across sound-speed samples.
root_dir = fileparts(fileparts(mfilename('fullpath')));
addpath('D:/COMSOL64/Multiphysics/mli');
mphstart('localhost', 2036);

source_mph = 'D:/桌面/codex/案例下载/COMSOL/房间的特征模态/eigenmodes_of_room.mph';
output_name = 'eigenmodes_of_room_target_mode_training.csv';
sound_speeds_m_s = [300, 320, 343, 360, 380];
reference_sound_speed_m_s = 343;
reference_target_frequency_Hz = 90;
if exist('sound_speeds_override', 'var'); sound_speeds_m_s = sound_speeds_override; end
if exist('output_name_override', 'var'); output_name = output_name_override; end

model = mphopen(source_mph);
rows = zeros(numel(sound_speeds_m_s), 3);
for index = 1:numel(sound_speeds_m_s)
    sound_speed = sound_speeds_m_s(index);
    expected_frequency_Hz = reference_target_frequency_Hz * sound_speed / reference_sound_speed_m_s;
    model.component('comp1').material('mat1').propertyGroup('def').set('soundspeed', {num2str(sound_speed, '%.15g')});
    model.study('std1').feature('eig').set('shift', num2str(expected_frequency_Hz, '%.15g'));
    model.study('std1').run;
    frequencies_Hz = real(mphglobal(model, 'freq', 'unit', 'Hz'));
    [~, mode_index] = min(abs(frequencies_Hz - expected_frequency_Hz));
    rows(index, :) = [sound_speed, expected_frequency_Hz, frequencies_Hz(mode_index)];
    fprintf('sound_speed=%g m/s, expected=%g Hz, tracked=%g Hz\n', rows(index, 1), rows(index, 2), rows(index, 3));
end

output_path = fullfile(root_dir, 'generated', 'training_runs', output_name);
if ~isfolder(fileparts(output_path)); mkdir(fileparts(output_path)); end
result = array2table(rows, 'VariableNames', {'sound_speed_m_s', 'expected_target_frequency_Hz', 'tracked_eigenfrequency_Hz'});
writetable(result, output_path);
disp(result);
