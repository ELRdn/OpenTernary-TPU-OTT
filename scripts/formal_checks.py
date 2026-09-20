#!/usr/bin/env python3
"""Combinational SAT proofs, not a sequential proof of the entire accelerator."""
from pathlib import Path
import subprocess,sys,os,time,json
root=Path(__file__).resolve().parents[1];os.chdir(root)
items=[('product_equivalence','rtl/tpc_ternary_product.sv formal/product_equivalence.sv'),
       ('t5_equivalence','rtl/tpc_radix3_decode5.sv formal/t5_equivalence.sv'),
       ('rne_equivalence','formal/rne_equivalence.sv')]
results=[]
for top,files in items:
    command=f'read_verilog -sv {files}; hierarchy -top {top}; proc; flatten; opt; memory_map; opt; sat -prove equal 1 -verify -show-inputs'
    start=time.time()
    with open(f'reports/formal_{top}.log','w') as log:
        run=subprocess.run([sys.executable,'scripts/yosys_driver.py',command],stdout=log,stderr=subprocess.STDOUT)
    text=Path(f'reports/formal_{top}.log').read_text()
    results.append({'property':top,'exit_code':run.returncode,'pass':run.returncode==0 and 'SUCCESS' in text,
                    'seconds':time.time()-start,'proof_scope':'combinational all inputs; two-state'})
Path('reports/formal_results.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
sys.exit(0 if all(x['pass'] for x in results) else 1)
