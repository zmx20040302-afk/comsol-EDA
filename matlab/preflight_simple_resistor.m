function preflight_simple_resistor(model_path, output_csv, error_txt)
try
    model = mphopen(model_path);
    model.study('std1').run;
    resistance_ohm = mphglobal(model, 'ec.R11', 'unit', 'ohm');
    result = table(resistance_ohm, 'VariableNames', {'resistance_ohm'});
    writetable(result, output_csv);
catch err
    file_id = fopen(error_txt, 'w');
    fprintf(file_id, '%s\n', getReport(err, 'extended', 'hyperlinks', 'off'));
    fclose(file_id);
    rethrow(err);
end
end
