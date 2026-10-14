function run_power_inductor_frequency_sweep(frequencies_Hz, output_name)
if nargin < 1 || isempty(frequencies_Hz), frequencies_Hz = [500 1000 2000 5000 10000 20000]; end
if nargin < 2 || isempty(output_name), output_name = 'power_inductor_frequency_training.csv'; end
project_root = fileparts(fileparts(mfilename('fullpath')));
output_csv = fullfile(project_root,'generated','training_runs',output_name);
log_path = replace(output_csv, '.csv', '.log');
addpath('D:\COMSOL64\Multiphysics\mli');
try, mphstart('localhost', 2036); catch exception, if ~contains(exception.message, 'Already connected'), rethrow(exception); end, end
source_mph = fullfile(project_root, 'generated', 'working_models', 'power_inductor_working.mph');
rows = zeros(0, 3); lines = strings(0, 1);
for index = 1:numel(frequencies_Hz)
    f = frequencies_Hz(index);
    try
        model = mphopen(source_mph);
        model.study('std1').feature('freq').set('plist', sprintf('%.12g[Hz]', f));
        model.study('std1').run;
        L = mphglobal(model, 'real(1/mef.Y11/mef.iomega)', 'dataset', 'dset1', 'solnum', 'end', 'unit', 'H');
        G = mphglobal(model, 'real(mef.Y11)', 'dataset', 'dset1', 'solnum', 'end', 'unit', 'S');
        rows(end+1,:) = [f L(end) G(end)]; %#ok<AGROW>
        lines(end+1,1) = sprintf('OK %.12g Hz L=%.12g H G=%.12g S', f, L(end), G(end)); %#ok<AGROW>
    catch exception
        lines(end+1,1) = sprintf('FAIL %.12g Hz :: %s', f, exception.message); %#ok<AGROW>
    end
    writelines(lines, log_path);
    writetable(array2table(rows, 'VariableNames', {'frequency_Hz','inductance_H','conductance_S'}), output_csv);
end
end
