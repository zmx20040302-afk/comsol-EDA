function preflight_tapered_cantilever(model_path, output_csv, error_txt)
try
    model = mphopen(model_path);
    model.study('std1').run;
    force_case_tip_displacement_m = mphinterp(model, 'sqrt(u^2+v^2)', ...
        'coord', [4; 2], 'solnum', 2, 'unit', 'm');
    result = table(force_case_tip_displacement_m, 'VariableNames', {'force_case_tip_displacement_m'});
    writetable(result, output_csv);
catch err
    file_id = fopen(error_txt, 'w');
    fprintf(file_id, '%s\n', getReport(err, 'extended', 'hyperlinks', 'off'));
    fclose(file_id);
    rethrow(err);
end
end
