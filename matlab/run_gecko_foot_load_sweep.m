function run_gecko_foot_load_sweep(model_path, load_points, output_name)
% Export COMSOL-computed gecko-foot stress, displacement, and strain responses.
% load_points columns: Fc in uN, Ff in uN, and contact angle in degrees.
project_root = fileparts(fileparts(mfilename('fullpath')));
if nargin < 1 || isempty(model_path)
    model_path = 'D:\桌面\codex\案例下载\电气\壁虎足\gecko_foot.mph';
end
if nargin < 2 || isempty(load_points)
    load_points = [
        0.20, 0.10, 60.0;
        0.20, 0.20, 60.0;
        0.20, 0.30, 60.0;
        0.40, 0.10, 60.0;
        0.40, 0.20, 60.0;
        0.40, 0.30, 60.0;
        0.60, 0.10, 60.0;
        0.60, 0.20, 60.0;
        0.60, 0.30, 60.0;
    ];
end
if nargin < 3 || isempty(output_name)
    output_name = 'gecko_foot_load_training.csv';
end
if size(load_points, 2) ~= 3 || isempty(load_points)
    error('gecko_foot:InvalidSweepPoints', ...
        'load_points must be a nonempty N-by-3 matrix: Fc_uN, Ff_uN, theta_deg.');
end
if any(~isfinite(load_points), 'all') || any(load_points(:, 1:2) <= 0, 'all')
    error('gecko_foot:InvalidSweepPoints', ...
        'Loads must be finite and strictly positive.');
end
if any(load_points(:, 3) <= 0 | load_points(:, 3) >= 180)
    error('gecko_foot:InvalidSweepPoints', ...
        'Contact angles must be strictly between 0 and 180 degrees.');
end

if ischar(output_name) || isstring(output_name)
    output_name = char(output_name);
else
    error('gecko_foot:InvalidOutputName', 'output_name must be a character vector or string.');
end
if numel(output_name) >= 2 && output_name(2) == ':'
    output_path = output_name;
else
    output_path = fullfile(project_root, 'generated', 'training_runs', output_name);
end
if ~isfolder(fileparts(output_path))
    mkdir(fileparts(output_path));
end

try
    addpath('D:\COMSOL64\Multiphysics\mli');
    mphstart('localhost', 2036);
    model = mphopen(model_path);
    row_count = size(load_points, 1);
    outputs = zeros(row_count, 6);
    for index = 1:row_count
        Fc_uN = load_points(index, 1);
        Ff_uN = load_points(index, 2);
        theta_deg = load_points(index, 3);
        model.param.set('Fc', sprintf('%.12g[uN]', Fc_uN));
        model.param.set('Ff', sprintf('%.12g[uN]', Ff_uN));
        model.param.set('theta', sprintf('%.12g*pi/180', theta_deg));
        model.study('std1').run;

        outputs(index, :) = [Fc_uN, Ff_uN, theta_deg, ...
            local_global_scalar(model, 'max_v_Mises', 'Pa'), ...
            local_global_scalar(model, 'max_disp', 'm'), ...
            local_global_scalar(model, 'max_ep1', '1')];
        fprintf('POINT=%d/%d Fc_uN=%.12g Ff_uN=%.12g theta_deg=%.12g max_v_Mises_Pa=%.12g max_disp_m=%.12g max_ep1=%.12g\n', ...
            index, row_count, outputs(index, 1), outputs(index, 2), outputs(index, 3), ...
            outputs(index, 4), outputs(index, 5), outputs(index, 6));
    end
    result = array2table(outputs, 'VariableNames', {
        'Fc_uN', 'Ff_uN', 'theta_deg', 'max_v_Mises_Pa', 'max_disp_m', 'max_ep1'});
    writetable(result, output_path);
    fprintf('SWEEP_CSV=%s\n', output_path);
catch err
    fprintf(2, 'GECKO_SWEEP_ERROR_IDENTIFIER=%s\n', err.identifier);
    fprintf(2, 'GECKO_SWEEP_ERROR_MESSAGE=%s\n', err.message);
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
