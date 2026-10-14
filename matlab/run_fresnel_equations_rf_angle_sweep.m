function run_fresnel_equations_rf_angle_sweep(angles_deg, output_name)
% Export COMSOL-computed TE/TM reflectance at specified incidence angles.
root_dir = fileparts(fileparts(mfilename('fullpath')));
source_mph = 'D:\桌面\codex\案例下载\电气\菲涅尔方程 (RF)\fresnel_equations.mph';
if nargin < 1 || isempty(angles_deg)
    angles_deg = [0, 10, 20, 30, 40, 50, 54, 56, 58, 60, 65, 70, 75];
end
if nargin < 2 || isempty(output_name)
    output_name = 'fresnel_equations_rf_training.csv';
end

addpath('D:\COMSOL64\Multiphysics\mli');
mphstart('localhost', 2036);
model = mphopen(source_mph);
rows = zeros(numel(angles_deg), 3);

for index = 1:numel(angles_deg)
    angle_deg = angles_deg(index);
    angle_expr = sprintf('%.12g[deg]', angle_deg);

    model.study('std1').feature('param').set('plistarr', {angle_expr});
    model.study('std1').run;
    reflectance_te = mphglobal(model, 'abs(emw.S11)^2', 'dataset', 'dset1', 'solnum', 'end');

    model.study('std2').feature('param').set('plistarr', {angle_expr});
    model.study('std2').run;
    reflectance_tm = mphglobal(model, 'abs(emw2.S11)^2', 'dataset', 'dset3', 'solnum', 'end');

    rows(index, :) = [angle_deg, reflectance_te(end), reflectance_tm(end)];
    fprintf('alpha=%g deg, R_TE=%.12g, R_TM=%.12g\n', angle_deg, reflectance_te(end), reflectance_tm(end));
end

output_path = fullfile(root_dir, 'generated', 'training_runs', output_name);
if ~isfolder(fileparts(output_path)); mkdir(fileparts(output_path)); end
result = array2table(rows, 'VariableNames', {'incident_angle_deg', 'TE_reflectance', 'TM_reflectance'});
writetable(result, output_path);
fprintf('SWEEP_CSV=%s\n', output_path);
end

