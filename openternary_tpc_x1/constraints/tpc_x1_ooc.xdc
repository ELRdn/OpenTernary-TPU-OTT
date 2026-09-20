# OOC engineering budgets, not board pin constraints. Not executed in this environment.
create_clock -name tpc_clk -period 4.000 [get_ports clk]
set_clock_uncertainty 0.100 [get_clocks tpc_clk]
set_input_delay -clock tpc_clk -max 0.500 [get_ports -filter {DIRECTION == IN && NAME != clk}]
set_input_delay -clock tpc_clk -min 0.000 [get_ports -filter {DIRECTION == IN && NAME != clk}]
set_output_delay -clock tpc_clk -max 0.500 [get_ports -filter {DIRECTION == OUT}]
set_output_delay -clock tpc_clk -min 0.000 [get_ports -filter {DIRECTION == OUT}]
