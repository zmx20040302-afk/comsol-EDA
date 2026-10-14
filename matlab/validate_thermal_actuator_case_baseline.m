% Baseline validation for the learned thermal-actuator Joule-heating case.
import com.comsol.model.util.*

mphstart('localhost', 2036);
case_path = 'D:/桌面/codex/案例下载/COMSOL/微执行器焦耳热 - 分布式参数版本/thermal_actuator_jh_distributed.mph';
model = mphopen(case_path);
% The exported case contains a cluster-computing feature with a stale batch path.
% Local CSV training must use the local solver instead.
try
  model.study('std1').feature.remove('cluco');
catch
end
model.study('std1').feature('param').set('pdistrib', false);
model.study('std1').feature('param').setIndex('pname', 'DV', 0);
model.study('std1').feature('param').setIndex('plistarr', '5[V]', 0);
model.study('std1').run;

Tmax_K = mphmax(model, 'T', 3);
project_root = fileparts(fileparts(mfilename('fullpath')));
result_dir = fullfile(project_root, 'generated', 'training_runs');
if ~isfolder(result_dir), mkdir(result_dir); end
result_path = fullfile(result_dir, 'thermal_actuator_baseline.csv');
writetable(table(5, Tmax_K, 'VariableNames', {'DV_V', 'Tmax_K'}), result_path);
ModelUtil.remove(model.tag());
fprintf('THERMAL_ACTUATOR_BASELINE_CSV=%s\n', result_path);


