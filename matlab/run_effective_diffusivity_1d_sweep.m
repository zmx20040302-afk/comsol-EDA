% Export D1-to-interior-concentration samples for the 1D homogenized diffusion model.
root_dir = fileparts(fileparts(mfilename('fullpath')));
addpath('D:/COMSOL64/Multiphysics/mli');
mphstart('localhost', 2036);

source_mph = 'D:/桌面/codex/案例下载/COMSOL/多孔材料的有效扩散系数/effective_diffusivity.mph';
output_name = 'effective_diffusivity_1d_training.csv';
diffusivities_m2_s = [1e-6, 1.5e-6, 2.15e-6, 3e-6, 4e-6];
if exist('diffusivities_override', 'var'); diffusivities_m2_s = diffusivities_override; end
if exist('output_name_override', 'var'); output_name = output_name_override; end

model = mphopen(source_mph);
rows = zeros(numel(diffusivities_m2_s), 2);
for index = 1:numel(diffusivities_m2_s)
    diffusivity = diffusivities_m2_s(index);
    model.param.set('D1', sprintf('%.15g[m^2/s]', diffusivity));
    model.study('std2').run;
    concentration = mphinterp(model, 'c2', 'coord', 2e-4, 'dataset', 'dset3', 't', 0.1, 'unit', 'mol/m^3');
    rows(index, :) = [diffusivity, concentration];
    fprintf('D1=%g m^2/s, c(0.2 mm,100 ms)=%g mol/m^3\n', diffusivity, concentration);
end

output_path = fullfile(root_dir, 'generated', 'training_runs', output_name);
if ~isfolder(fileparts(output_path)); mkdir(fileparts(output_path)); end
result = array2table(rows, 'VariableNames', {'D1_m2_s', 'concentration_x0p2mm_t100ms_mol_m3'});
writetable(result, output_path);
disp(result);
