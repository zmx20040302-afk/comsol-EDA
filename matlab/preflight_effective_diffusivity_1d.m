% Validate a reproducible 1D homogenized porous-diffusion output before sampling.
root_dir = fileparts(fileparts(mfilename('fullpath')));
addpath('D:/COMSOL64/Multiphysics/mli');
mphstart('localhost', 2036);

source_mph = 'D:/桌面/codex/案例下载/COMSOL/多孔材料的有效扩散系数/effective_diffusivity.mph';
model = mphopen(source_mph);
model.study('std2').run;
outlet_concentration_100ms_mol_m3 = mphinterp(model, 'c2', 'coord', 8e-4, 'dataset', 'dset3', 't', 0.1, 'unit', 'mol/m^3');

output_path = fullfile(root_dir, 'generated', 'training_runs', 'effective_diffusivity_1d_baseline.csv');
if ~isfolder(fileparts(output_path)); mkdir(fileparts(output_path)); end
result = table(2.15e-6, outlet_concentration_100ms_mol_m3, 'VariableNames', {'D1_m2_s', 'outlet_concentration_100ms_mol_m3'});
writetable(result, output_path);
disp(result);
