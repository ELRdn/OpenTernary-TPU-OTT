"""Build and validate the narrowed-RNE design in the current task session."""
from pathlib import Path
import subprocess,sys,os,time,json
root=Path(__file__).resolve().parents[1];os.chdir(root)
start=time.time();stages=[]
def run(cmd,log):
    before=time.time()
    with open(log,'w') as f:
        p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
    stages.append({'command':cmd,'exit_code':p.returncode,'seconds':time.time()-before})
    Path('reports/validation_progress.json').write_text(json.dumps(stages,indent=2))
    if p.returncode:raise SystemExit(p.returncode)
script='read_verilog -sv rtl/*.sv; hierarchy -check -top tpc_accelerator; proc; opt; memory_collect; check -assert; write_cxxrtl -noflatten -O2 -g0 -header build/accelerator.cc'
run([sys.executable,'scripts/yosys_driver.py',script],'reports/cxxrtl_generation.log')
run([sys.executable,'scripts/compile_optimized.py'],'reports/compile_launcher.log')
# Technology mapping is independent of simulation, with both results collected.
synlog=open('reports/synth_launcher.log','w')
syn=subprocess.Popen([sys.executable,'scripts/synth_xcup.py'],stdout=synlog,stderr=subprocess.STDOUT)
run([sys.executable,'-m','pytest','tests/test_rtl.py','-q','--junitxml=reports/rtl_pytest.xml'],'reports/rtl_pytest.log')
rc=syn.wait();synlog.close()
stages.append({'command':['scripts/synth_xcup.py'],'exit_code':rc})
Path('reports/optimized_validation.json').write_text(json.dumps({'seconds':time.time()-start,'stages':stages},indent=2))
raise SystemExit(rc)
