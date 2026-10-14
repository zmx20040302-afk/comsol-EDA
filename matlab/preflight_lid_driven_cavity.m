% Validate a single low-Reynolds-number lid-driven-cavity solve before sampling.
root_dir = fileparts(fileparts(mfilename('fullpath')));
addpath('D:/COMSOL64/Multiphysics/mli');
mphstart('localhost', 2036);

source_mph = 'D:/桌面/codex/案例下载/COMSOL/顶盖驱动方腔流/lid_driven_cavity.mph';
model = mphopen(source_mph);
model.param.set('Re', '100');
model.study('std1').feature('stat').set('useparam', false);
model.study('std1').run;

u_mid_upper_m_s = mphinterp(model, 'u', 'coord', [0.5; 0.75], 'unit', 'm/s');
v_mid_upper_m_s = mphinterp(model, 'v', 'coord', [0.5; 0.75], 'unit', 'm/s');
speed_mid_upper_m_s = sqrt(u_mid_upper_m_s^2 + v_mid_upper_m_s^2);

output_path = fullfile(root_dir, 'generated', 'training_runs', 'lid_driven_cavity_baseline.csv');
if ~isfolder(fileparts(output_path)); mkdir(fileparts(output_path)); end
result = table(100, u_mid_upper_m_s, v_mid_upper_m_s, speed_mid_upper_m_s, ...
    'VariableNames', {'Re', 'u_mid_upper_m_s', 'v_mid_upper_m_s', 'speed_mid_upper_m_s'});
writetable(result, output_path);
disp(result);
