function run_thermal_actuator_simplified_sweep(model_path, output_csv, dv_values, htc_s_values, htc_us_value)
% Run a bounded two-parameter COMSOL sweep without modifying the source MPH file.
import com.comsol.model.*
import com.comsol.model.util.*

model = mphopen(model_path);
rows = zeros(numel(dv_values) * numel(htc_s_values), 6);
index = 1;
for dv = dv_values
    for htc_s = htc_s_values
        model.param.set('DV', sprintf('%.12g[V]', dv));
        model.param.set('htc_s', sprintf('%.12g[W/(m^2*K)]', htc_s));
        model.param.set('htc_us', sprintf('%.12g[W/(m^2*K)]', htc_us_value));
        model.study('std1').run;
        rows(index,:) = [dv, htc_s, htc_us_value, mphmax(model, 'T', 3), mphmax(model, 'solid.disp', 3, 'unit', 'm'), mphint2(model, 'ec.Qh', 3)];
        index = index + 1;
    end
end

result = array2table(rows, 'VariableNames', {'DV_V','htc_s_W_m2K','htc_us_W_m2K','Tmax_K','umax_m','joule_power_W'});
writetable(result, output_csv);
end

