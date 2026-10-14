function run_circuit_fem_resistor_sweep(model_path, output_csv, sigma_values)
% Run independent stationary COMSOL points for the circuit-FEM resistor model.
model = mphopen(model_path);
row_count = numel(sigma_values);
sigma_S_m = zeros(row_count, 1);
resistance_circuit_ohm = zeros(row_count, 1);
resistance_analytic_ohm = zeros(row_count, 1);
for index = 1:row_count
    sigma_S_m(index) = sigma_values(index);
    model.param.set('sigma', sprintf('%.12g[S/m]', sigma_S_m(index)));
    model.study('std1').run;
    resistance_circuit_ohm(index) = mphglobal(model, '((cir.v_2-cir.v_1)/cir.R1.v)*R1');
    resistance_analytic_ohm(index) = mphglobal(model, 'L/(pi*r^2*sigma)');
end
result = table(sigma_S_m, resistance_circuit_ohm, resistance_analytic_ohm);
writetable(result, output_csv);
end