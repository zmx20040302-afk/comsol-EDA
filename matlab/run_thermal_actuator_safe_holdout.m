% Generate independent midpoint validation data for the thermal-actuator surrogate.
import com.comsol.model.util.*

mphstart('localhost', 2036);
case_path = 'D:/桌面/codex/案例下载/COMSOL/微执行器焦耳热 - 分布式参数版本/thermal_actuator_jh_distributed.mph';
model = mphopen(case_path);
try
  model.study('std1').feature.remove('cluco');
catch
end
model.study('std1').feature('param').set('pdistrib', false);

samples = [2.5 17500 350; 2.5 22500 450; 3.5 17500 450; 3.5 22500 350];
rows = zeros(size(samples, 1), 5);
for index = 1:size(samples, 1)
  DV = samples(index, 1); htc_s = samples(index, 2); htc_us = samples(index, 3);
  model.param.set('DV', sprintf('%.12g[V]', DV));
  model.param.set('htc_s', sprintf('%.12g[W/(m^2*K)]', htc_s));
  model.param.set('htc_us', sprintf('%.12g[W/(m^2*K)]', htc_us));
  model.study('std1').feature('param').setIndex('pname', 'DV', 0);
  model.study('std1').feature('param').setIndex('plistarr', sprintf('%.12g[V]', DV), 0);
  model.study('std1').run;
  rows(index,:) = [DV htc_s htc_us mphmax(model, 'T', 3) mphint2(model, 'ec.Qh', 3)];
end

project_root = fileparts(fileparts(mfilename('fullpath')));
result_dir = fullfile(project_root, 'generated', 'training_runs');
if ~isfolder(result_dir), mkdir(result_dir); end
output_csv = fullfile(result_dir, 'thermal_actuator_safe_holdout.csv');
validation_table = array2table(rows, 'VariableNames', {'DV_V','htc_s_W_m2K','htc_us_W_m2K','Tmax_K','joule_power_W'});
writetable(validation_table, output_csv);
ModelUtil.remove(model.tag());
fprintf('THERMAL_ACTUATOR_SAFE_HOLDOUT_CSV=%s\n', output_csv);
