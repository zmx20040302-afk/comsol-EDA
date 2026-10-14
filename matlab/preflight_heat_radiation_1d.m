function preflight_heat_radiation_1d(model_path, output_csv, error_txt)
try
    model = mphopen(model_path);
    model.study('std1').run;
    radiating_end_temperature_K = mphinterp(model, 'T', 'coord', 0.1, 'unit', 'K');
    result = table(radiating_end_temperature_K, 'VariableNames', {'radiating_end_temperature_K'});
    writetable(result, output_csv);
catch err
    file_id = fopen(error_txt, 'w');
    fprintf(file_id, '%s\n', getReport(err, 'extended', 'hyperlinks', 'off'));
    fclose(file_id);
    rethrow(err);
end
end
