function preflight_gecko_foot(model_path, output_csv)
% Confirm the saved gecko-foot model solves and exposes scalar structural outputs.
project_root = fileparts(fileparts(mfilename('fullpath')));
if nargin < 1 || isempty(model_path)
    model_path = 'D:\桌面\codex\案例下载\电气\壁虎足\gecko_foot.mph';
end
if nargin < 2 || isempty(output_csv)
    output_csv = fullfile(project_root, 'generated', 'training_runs', 'gecko_foot_preflight.csv');
end

if ~isfolder(fileparts(output_csv))
    mkdir(fileparts(output_csv));
end

try
    addpath('D:\COMSOL64\Multiphysics\mli');
    mphstart('localhost', 2036);
    model = mphopen(model_path);
    model.study('std1').run;

    max_v_Mises_Pa = local_global_scalar(model, 'max_v_Mises', 'Pa');
    max_disp_m = local_global_scalar(model, 'max_disp', 'm');
    max_ep1 = local_global_scalar(model, 'max_ep1', '1');
    result = table(0.4, 0.2, 60.0, max_v_Mises_Pa, max_disp_m, max_ep1, ...
        'VariableNames', {'Fc_uN', 'Ff_uN', 'theta_deg', ...
        'max_v_Mises_Pa', 'max_disp_m', 'max_ep1'});
    writetable(result, output_csv);
    fprintf('PREFLIGHT_CSV=%s\n', output_csv);
    fprintf('GECKO_BASELINE max_v_Mises_Pa=%.12g max_disp_m=%.12g max_ep1=%.12g\n', ...
        max_v_Mises_Pa, max_disp_m, max_ep1);
catch err
    fprintf(2, 'GECKO_PREFLIGHT_ERROR_IDENTIFIER=%s\n', err.identifier);
    fprintf(2, 'GECKO_PREFLIGHT_ERROR_MESSAGE=%s\n', err.message);
    rethrow(err);
end
end

function value = local_global_scalar(model, expression, unit)
value = double(mphglobal(model, expression, 'unit', unit));
if isempty(value) || ~isfinite(value(1))
    error('gecko_foot:InvalidScalarOutput', ...
        'COMSOL expression %s did not return a finite scalar.', expression);
end
value = value(1);
end
