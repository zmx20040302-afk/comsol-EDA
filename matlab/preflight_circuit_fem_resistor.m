function preflight_circuit_fem_resistor(model_path, output_csv)
% Read existing circuit-FEM solution and export named global scalar outputs in SI units.
model = mphopen(model_path);
expressions = {'cir.v_0', 'cir.v_1', 'cir.v_2', 'cir.v_3', '((cir.v_2-cir.v_1)/cir.R1.v)*R1', 'L/(pi*r^2*sigma)'};
values = zeros(1, numel(expressions));
for index = 1:numel(expressions)
    values(index) = mphglobal(model, expressions{index});
end
voltage_node_0_V = values(1);
voltage_node_1_V = values(2);
voltage_node_2_V = values(3);
voltage_node_3_V = values(4);
resistance_circuit_ohm = values(5);
resistance_analytic_ohm = values(6);
result = table(voltage_node_0_V, voltage_node_1_V, voltage_node_2_V, voltage_node_3_V, resistance_circuit_ohm, resistance_analytic_ohm);
writetable(result, output_csv);
end