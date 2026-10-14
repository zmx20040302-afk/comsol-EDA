function preflight_power_inductor_frequency()
addpath('D:\COMSOL64\Multiphysics\mli');
try
    mphstart('localhost', 2036);
catch exception
    if ~contains(exception.message, 'Already connected')
        rethrow(exception);
    end
end
model = mphopen('D:\桌面\codex\案例下载\电气\功率电感器的电感\power_inductor.mph');
for frequency_Hz = [1000, 10000]
    model.study('std1').feature('freq').set('plist', sprintf('%.12g[Hz]', frequency_Hz));
    model.study('std1').run;
    inductance_H = mphglobal(model, 'real(1/mef.Y11/mef.iomega)', 'dataset', 'dset1', 'solnum', 'end', 'unit', 'H');
    conductance_S = mphglobal(model, 'real(mef.Y11)', 'dataset', 'dset1', 'solnum', 'end', 'unit', 'S');
    fprintf('FREQ=%.12g Hz L=%.12g H G=%.12g S\n', frequency_Hz, inductance_H(end), conductance_S(end));
end
end
