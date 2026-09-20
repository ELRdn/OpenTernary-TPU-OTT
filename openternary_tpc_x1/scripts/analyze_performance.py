#!/usr/bin/env python3
"""Analytical roofline and measured RTL cycle counts. No claims of measured MHz/tokens/s."""
from pathlib import Path
import json,csv,math
ROOT=Path(__file__).resolve().parents[1]
cfg=json.loads((ROOT/'config/edge_x1.json').read_text())
frequency=250e6
rows,lanes,batch,group=16,16,4,128
measurements=json.loads((ROOT/'reports/rtl_cycle_measurements.json').read_text()) if (ROOT/'reports/rtl_cycle_measurements.json').exists() else None
result={
 'evidence_class':'analytical projections with separately labeled actual RTL cycles',
 'assumed_clock_hz':frequency,'clock_verified_by_place_route':False,
 'gemm_peak_terms_per_cycle':rows*lanes*batch,'gemv_peak_active_terms_per_cycle':rows*lanes,
 'gemm_peak_mac_equivalent_tops':2*rows*lanes*batch*frequency/1e12,
 'gemv_peak_mac_equivalent_tops':2*rows*lanes*frequency/1e12,
 'mac_equivalent_operations_per_term':2,'actual_floating_point_operations':False,
 'weight_bytes_per_input_beat':rows*lanes*2/8,
 'coefficient_bytes_per_group':rows*4,
 'amortized_weight_and_coefficient_bytes_per_input_beat':rows*lanes*(2/8+4/group),
 'continuous_weight_and_scale_bandwidth_gbps':rows*lanes*(2/8+4/group)*frequency/1e9,
 'ddr_peak_gbps_from_baseline_paper':19.2,'ddr_efficiency_assumption':0.70,
 'ddr_effective_gbps_assumed':13.44,
 'bandwidth_limited_duty_ceiling_excluding_other_traffic':13.44/18,
 'T5_DMA_integrated':False,'nonlinear_LLM_hardware_integrated':False,
 'end_to_end_tokens_s_measured':None,'power_w_measured':None,
 'cached_tile_measurements':measurements,
 'logical_scratchpad_bytes':{'activation':16384,'weights_double_buffer':32768,'scale_double_buffer':4096},
 'TeLLMe_target':{'model':'same 0.7B checkpoint required, not yet obtained',
   'short_context_decode_tokens_s':12,'prefill_64_seconds':0.45,
   '1024_context_decode_tokens_s':10,'power_w':6.72,
   'power_boundary':'must first resolve baseline measurement boundary',
   'status':'NOT_ACHIEVED_NOT_MEASURED'},
}
if measurements:
 for item in measurements['records']:
  item['conditional_gterms_s']=item['active_terms']/item['cycles']*frequency/1e9
  item['conditional_mac_equivalent_tops']=2*item['active_terms']/item['cycles']*frequency/1e12
# A-stationary loop: repeat weights per ceil(B/4), not magically across all tokens.
dse=[]
for r in [4,8,16,32]:
 for l in [4,8,16,32]:
  for b in [1,2,4]:
   weight_rate=r*l*(2/8+4/128)*frequency/1e9
   terms=r*l*b
   # This is a concrete RTL storage-count proxy, NOT an FPGA-LUT estimate.
   tree_register_bits=sum((l>>level)*(9+level) for level in range(l.bit_length()))*r*b
   dse.append({'R':r,'L':l,'B':b,'terms_per_cycle':terms,'peak_tops_equivalent':2*terms*frequency/1e12,
      'weight_scale_gbps':weight_rate,'ddr_duty_ceiling':min(1,13.44/weight_rate),
      'dot_pipeline_data_register_bits_proxy':tree_register_bits,'actually_synthesized':r==16 and l==16 and b==4})
with (ROOT/'reports/analytical_design_space.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(dse[0]));w.writeheader();w.writerows(dse)
(ROOT/'reports/performance_analysis.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='cached_tile_measurements'},indent=2))
