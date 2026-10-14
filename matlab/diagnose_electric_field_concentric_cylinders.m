function diagnose_electric_field_concentric_cylinders(model_path, output_csv, error_txt)
try
    model = mphopen(model_path);
    model.study('std1').run;
    % The source geometry is a one-dimensional axisymmetric radial interval.
    potential_mid_V = mphinterp(model, 'V', 'coord', 0.5, 'unit', 'V');
    dr = 1e-4;
    potential_plus_V = mphinterp(model, 'V', 'coord', 0.5 + dr, 'unit', 'V');
    potential_minus_V = mphinterp(model, 'V', 'coord', 0.5 - dr, 'unit', 'V');
    electric_field_mid_V_m = -(potential_plus_V - potential_minus_V) / (2 * dr);
    result = table(potential_mid_V, electric_field_mid_V_m, ...
        'VariableNames', {'potential_mid_V', 'electric_field_mid_V_m'});
    writetable(result, output_csv);
catch err
    file_id = fopen(error_txt, 'w');
    fprintf(file_id, '%s\n', getReport(err, 'extended', 'hyperlinks', 'off'));
    fclose(file_id);
    rethrow(err);
end
end
