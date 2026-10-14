% Export declared-scope COMSOL samples for a lid-driven-cavity surrogate.
root_dir = fileparts(fileparts(mfilename('fullpath')));
addpath('D:/COMSOL64/Multiphysics/mli');
mphstart('localhost', 2036);

source_mph = 'D:/桌面/codex/案例下载/COMSOL/顶盖驱动方腔流/lid_driven_cavity.mph';
output_name = 'lid_driven_cavity_re_training.csv';
reynolds_numbers = [50, 100, 200, 400, 800];
if exist('reynolds_numbers_override', 'var'); reynolds_numbers = reynolds_numbers_override; end
if exist('output_name_override', 'var'); output_name = output_name_override; end

model = mphopen(source_mph);
model.study('std1').feature('stat').set('useparam', false);
rows = zeros(numel(reynolds_numbers), 4);
for index = 1:numel(reynolds_numbers)
    re_value = reynolds_numbers(index);
    model.param.set('Re', num2str(re_value, '%.15g'));
    model.study('std1').run;
    u_value = mphinterp(model, 'u', 'coord', [0.5; 0.75], 'unit', 'm/s');
    v_value = mphinterp(model, 'v', 'coord', [0.5; 0.75], 'unit', 'm/s');
    rows(index, :) = [re_value, u_value, v_value, sqrt(u_value^2 + v_value^2)];
    fprintf('Re=%g, speed=%g m/s\n', re_value, rows(index, 4));
end

output_path = fullfile(root_dir, 'generated', 'training_runs', output_name);
if ~isfolder(fileparts(output_path)); mkdir(fileparts(output_path)); end
result = array2table(rows, 'VariableNames', {'Re', 'u_mid_upper_m_s', 'v_mid_upper_m_s', 'speed_mid_upper_m_s'});
writetable(result, output_path);
disp(result);
