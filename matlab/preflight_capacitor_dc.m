function preflight_capacitor_dc(model_path, output_csv, error_txt)
try
    model = mphopen(model_path);
    model.study('std1').run;
    capacitance_F = mphglobal(model, 'es.C11', 'unit', 'F');
    result = table(capacitance_F, 'VariableNames', {'capacitance_F'});
    writetable(result, output_csv);
catch err
    file_id = fopen(error_txt, 'w');
    fprintf(file_id, '%s\n', getReport(err, 'extended', 'hyperlinks', 'off'));
    fclose(file_id);
    rethrow(err);
end
end
