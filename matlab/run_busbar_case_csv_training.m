% Export training data from the learned busbar Joule-heating case.
% This wrapper preserves the case's own parametric variables and solves it
% through the local COMSOL mphserver before writing a compact CSV dataset.

import com.comsol.model.util.*

case_dir = 'D:/桌面/codex/案例下载/COMSOL/母线板装配的焦耳热';
addpath(case_dir);
mphstart('localhost', 2036);

m = model();
m.component('comp1').cpl.create('maxop_csv', 'Maximum');
m.component('comp1').cpl('maxop_csv').selection.all;
m.study('std1').run;

r_d_mm = mphglobal(m, 'r_d', 'dataset', 'dset2', 'solnum', 'all')' * 1e3;
a_c_w_mm = mphglobal(m, 'a_c_w', 'dataset', 'dset2', 'solnum', 'all')' * 1e3;
Tmax_K = mphglobal(m, 'maxop_csv(T)', 'dataset', 'dset2', 'solnum', 'all')';

training_table = table(r_d_mm, a_c_w_mm, Tmax_K);
output_csv = fullfile(pwd, 'generated', 'training_runs', 'busbar_assembly_case_training.csv');
writetable(training_table, output_csv);
ModelUtil.remove(m.tag());
fprintf('BUSBAR_TRAINING_CSV=%s\n', output_csv);
