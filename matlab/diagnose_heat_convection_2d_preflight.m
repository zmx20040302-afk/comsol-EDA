function diagnose_heat_convection_2d_preflight(model_path, output_csv, error_txt)
try
    preflight_heat_convection_2d(model_path, output_csv);
catch err
    file_id = fopen(error_txt, 'w');
    fprintf(file_id, '%s\n', err.message);
    for index = 1:numel(err.stack)
        fprintf(file_id, '%s:%d\n', err.stack(index).name, err.stack(index).line);
    end
    fclose(file_id);
    rethrow(err);
end
end