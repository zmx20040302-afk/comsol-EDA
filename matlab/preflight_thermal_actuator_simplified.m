function preflight_thermal_actuator_simplified(model_path, output_csv)
% Read only an existing MPH solution and export candidate scalar outputs.
import com.comsol.model.*
import com.comsol.model.util.*

model = mphopen(model_path);
Tmax_K = mphmax(model, 'T', 3);
try
    umax_m = mphmax(model, 'solid.disp', 3, 'unit', 'm');
catch
    umax_m = NaN;
end
try
    joule_power_W = mphint2(model, 'ec.Qh', 3);
catch
    joule_power_W = NaN;
end

result = table(Tmax_K, umax_m, joule_power_W);
writetable(result, output_csv);
end

