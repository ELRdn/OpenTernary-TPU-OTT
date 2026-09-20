# NOT RUN here. Set FPGA_PART to the exact board part supported by your Vivado installation.
# vivado -mode batch -source scripts/synth_vivado.tcl
if {![info exists ::env(FPGA_PART)]} { error "FPGA_PART is required; do not guess the target part" }
set root [file normalize [file join [file dirname [info script]] ..]]
cd $root
file mkdir reports/vivado
read_verilog -sv [glob rtl/*.sv]
read_xdc constraints/tpc_x1_ooc.xdc
synth_design -top tpc_accelerator -part $::env(FPGA_PART) -mode out_of_context
opt_design
place_design
phys_opt_design
route_design
report_utilization -hierarchical -file reports/vivado/utilization.rpt
report_timing_summary -report_unconstrained -check_timing_verbose -file reports/vivado/timing.rpt
redirect -file reports/vivado/check_timing.rpt {check_timing -verbose}
write_checkpoint -force reports/vivado/routed.dcp
set paths [get_timing_paths -max_paths 1 -delay_type max]
if {[llength $paths] == 0} {error "No timing paths: constraint/clock setup must be fixed"}
set slack [get_property SLACK [lindex $paths 0]]
puts "OOC_SETUP_SLACK_NS=$slack; NOT A BOARD MEASUREMENT; review unconstrained paths"
if {$slack < 0} {error "250 MHz OOC timing target NOT met"}
# No bitstream or fabricated power report is produced by this script.
# A passing internal timing report still requires wrapper/CDC/board validation.
