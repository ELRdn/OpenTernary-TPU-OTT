#!/usr/bin/env python3
"""Real technology mapping, NOT place-and-route or power measurement."""
from pathlib import Path
import subprocess,sys,os,time,json
root=Path(__file__).resolve().parents[1];os.chdir(root)
start=time.time()
try:
    import pyosys
    os.environ['PATH']=str(Path(pyosys.__file__).parent)+os.pathsep+os.environ['PATH']
except ImportError:
    pass
script=('read_verilog -sv rtl/*.sv; '
        'synth_xilinx -family xcup -top tpc_accelerator -noiopad -noclkbuf '
        '-json build/tpc_x1_xcup.json; '
        'tee -o reports/synthesis_stat.json stat -json -tech xilinx; '
        'write_verilog -noattr build/tpc_x1_xcup.v')
with open('reports/synthesis_xcup.log','w') as f:
    result=subprocess.run([sys.executable,'scripts/yosys_driver.py',script],stdout=f,stderr=subprocess.STDOUT)
Path('reports/synthesis_run.json').write_text(json.dumps({'exit_code':result.returncode,'seconds':time.time()-start,
    'mapping':'Xilinx UltraScale+ / Yosys synth_xilinx -family xcup',
    'place_and_route':False,'clock_verified':False,'power_measured':False},indent=2))
sys.exit(result.returncode)
