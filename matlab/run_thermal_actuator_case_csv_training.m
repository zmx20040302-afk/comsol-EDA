% Generate bounded CSV training data from the learned thermal-actuator case.
import com.comsol.model.util.*

mphstart('localhost', 2036);
case_path = 'D:/桌面/codex/案例下载/COMSOL/微执行器焦耳热 - 分布式参数版本/thermal_actuator_jh_distributed.mph';
model = mphopen(case_path);
try
  model.study('std1').feature.remove('cluco');
catch
end
model.study('std1').feature('param').set('pdistrib', false);

DV_values = [5 10 15];
htc_s_values = [15000 20000 25000];
htc_us_values = [300 400 500];
rows = zeros(numel(DV_values) * numel(htc_s_values) * numel(htc_us_values), 5);
index = 1;
for DV = DV_values
  for htc_s = htc_s_values
    for htc_us = htc_us_values
      model.param.set('DV', sprintf('%.12g[V]', DV));
      model.param.set('htc_s', sprintf('%.12g[W/(m^2*K)]', htc_s));
      model.param.set('htc_us', sprintf('%.12g[W/(m^2*K)]', htc_us));
      model.study('std1').feature('param').setIndex('pname', 'DV', 0);
      model.study('std1').feature('param').setIndex('plistarr', sprintf('%.12g[V]', DV), 0);
      model.study('std1').run;
      rows(index,:) = [DV htc_s htc_us mphmax(model, 'T', 3) mphint2(model, 'ec.Qh', 3)];
      fprintf('THERMAL_ACTUATOR_SAMPLE=%d/%d\n', index, size(rows, 1));
      index = index + 1;
    end
  end
end

project_root = fileparts(fileparts(mfilename('fullpath')));
result_dir = fullfile(project_root, 'generated', 'training_runs');
if ~isfolder(result_dir), mkdir(result_dir); end
output_csv = fullfile(result_dir, 'thermal_actuator_case_training.csv');
training_table = array2table(rows, 'VariableNames', {'DV_V','htc_s_W_m2K','htc_us_W_m2K','Tmax_K','joule_power_W'});
writetable(training_table, output_csv);
ModelUtil.remove(model.tag());
fprintf('THERMAL_ACTUATOR_TRAINING_CSV=%s\n', output_csv);
