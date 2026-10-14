function diagnose_pn_junction_current_variables()
% Discover a valid P-N-junction current-density result expression from COMSOL.
project_root = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\P-N 结 - 一维\pn_junction_1d.mph';
output_txt = fullfile(project_root, 'generated', 'training_runs', 'pn_junction_current_variable_diagnosis.txt');

addpath('D:\COMSOL64\Multiphysics\mli');
mphstart('localhost', 2036);
model = mphopen(source_mph);
model.param.set('bias', '0.5[V]');
model.param.set('sweep', '1');
model.study('std1').feature('stat').set('plistarr', {'0.5' '1'});
model.study('std1').run;

expressions = {'semi.JnX', 'semi.JpX', 'semi.JnX+semi.JpX', 'semi.Jn_x', 'semi.Jp_x', 'semi.Jn_x+semi.Jp_x', 'semi.JX', 'semi.J', 'semi.Jn1', 'semi.Jp1'};
lines = strings(0, 1);
for index = 1:numel(expressions)
    expression = expressions{index};
    try
        value = mphinterp(model, expression, 'coord', 2.5e-6, 'dataset', 'dset1', 'solnum', 'end');
        line = sprintf('OK %s = %.12g', expression, value(end));
    catch exception
        line = sprintf('FAIL %s :: %s', expression, exception.message);
    end
    lines(end + 1, 1) = string(line); %#ok<AGROW>
    fprintf('%s\n', line);
end
writelines(lines, output_txt);
fprintf('DIAGNOSIS_FILE=%s\n', output_txt);
end
