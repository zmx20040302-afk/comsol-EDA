function run_thermal_actuator_augmentation_plan(plan_path, output_csv)
% Run a registered micro-actuator augmentation plan and export COMSOL results.
if nargin < 1 || strlength(string(plan_path)) == 0
    error('plan_path is required');
end
if nargin < 2 || strlength(string(output_csv)) == 0
    error('output_csv is required');
end

import com.comsol.model.util.*

plan = jsondecode(fileread(plan_path));
samples = plan.recommended_comsol_samples;
if ~isstruct(samples) || isempty(samples)
    error('The augmentation plan has no recommended COMSOL samples.');
end

mphstart('localhost', 2036);
case_path = 'D:/桌面/codex/案例下载/COMSOL/微执行器焦耳热 - 分布式参数版本/thermal_actuator_jh_distributed.mph';
model = mphopen(case_path);
try
    model.study('std1').feature.remove('cluco');
catch
end
model.study('std1').feature('param').set('pdistrib', false);

rows = zeros(numel(samples), 5);
for index = 1:numel(samples)
    sample = samples(index);
    DV = sample.DV_V;
    htc_s = sample.htc_s_W_m2K;
    htc_us = sample.htc_us_W_m2K;
    model.param.set('DV', sprintf('%.12g[V]', DV));
    model.param.set('htc_s', sprintf('%.12g[W/(m^2*K)]', htc_s));
    model.param.set('htc_us', sprintf('%.12g[W/(m^2*K)]', htc_us));
    model.study('std1').feature('param').setIndex('pname', 'DV', 0);
    model.study('std1').feature('param').setIndex('plistarr', sprintf('%.12g[V]', DV), 0);
    model.study('std1').run;
    rows(index,:) = [DV htc_s htc_us mphmax(model, 'T', 3) mphint2(model, 'ec.Qh', 3)];
    fprintf('THERMAL_ACTUATOR_AUGMENTATION_SAMPLE=%d/%d\n', index, numel(samples));
end

result_dir = fileparts(output_csv);
if ~isfolder(result_dir), mkdir(result_dir); end
result_table = array2table(rows, 'VariableNames', {'DV_V','htc_s_W_m2K','htc_us_W_m2K','Tmax_K','joule_power_W'});
writetable(result_table, output_csv);
ModelUtil.remove(model.tag());
fprintf('THERMAL_ACTUATOR_AUGMENTATION_CSV=%s\n', output_csv);
end
