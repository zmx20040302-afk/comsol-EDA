% Inspect the full eigenfrequency lists to define a stable modal-tracking rule.
addpath('D:/COMSOL64/Multiphysics/mli');
mphstart('localhost', 2036);
source_mph = 'D:/桌面/codex/案例下载/COMSOL/房间的特征模态/eigenmodes_of_room.mph';
model = mphopen(source_mph);
for sound_speed = [300, 343, 380]
    model.component('comp1').material('mat1').propertyGroup('def').set('soundspeed', {num2str(sound_speed, '%.15g')});
    model.study('std1').feature('eig').set('shift', '90');
    model.study('std1').run;
    frequencies_Hz = mphglobal(model, 'freq', 'unit', 'Hz');
    fprintf('sound_speed=%g Hz_list=', sound_speed);
    fprintf(' %.10g', real(frequencies_Hz));
    fprintf('\n');
end
