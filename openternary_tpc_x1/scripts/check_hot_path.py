from pathlib import Path
import subprocess,sys,json,os
root=Path(__file__).resolve().parents[1];os.chdir(root)
cmd='read_verilog -sv rtl/*.sv; hierarchy -check -top tpc_tile_mac; proc; opt; flatten; opt; check -assert; select -assert-none t:$mul t:$macc t:$div t:$mod; stat'
with open('reports/hot_path_structure.log','w') as f:
 p=subprocess.run([sys.executable,'scripts/yosys_driver.py',cmd],stdout=f,stderr=subprocess.STDOUT)
Path('reports/hot_path_structure.json').write_text(json.dumps({
 'top':'tpc_tile_mac','pass':p.returncode==0,'proof':'Yosys flattened generic structural cell exclusion',
 'forbidden_cell_types':['$mul','$macc','$div','$mod'],
 'scope_excludes_group_scale':True},indent=2))
raise SystemExit(p.returncode)
