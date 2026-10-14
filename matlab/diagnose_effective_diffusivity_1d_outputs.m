% Find an informative concentration observable for the homogenized diffusion model.
addpath('D:/COMSOL64/Multiphysics/mli');
mphstart('localhost', 2036);
model = mphopen('D:/桌面/codex/案例下载/COMSOL/多孔材料的有效扩散系数/effective_diffusivity.mph');
model.study('std2').run;
for time_s = [0.002, 0.01, 0.05, 0.1]
    values = mphinterp(model, 'c2', 'coord', [0, 2e-4, 4e-4, 6e-4, 8e-4], 'dataset', 'dset3', 't', time_s, 'unit', 'mol/m^3');
    fprintf('t=%g s, c2=', time_s);
    fprintf(' %.8g', values);
    fprintf('\n');
end
