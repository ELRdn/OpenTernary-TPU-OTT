#!/usr/bin/env python3
"""Compile actual SystemVerilog with official Yosys/CXXRTL; reject stale binaries."""
from pathlib import Path
import subprocess,sys,os,shutil,time,json,hashlib,importlib.metadata
ROOT=Path(__file__).resolve().parents[1]
def main():
    os.chdir(ROOT);(ROOT/'build').mkdir(exist_ok=True);(ROOT/'reports').mkdir(exist_ok=True)
    try:import pyosys
    except ImportError:raise SystemExit('Install pyosys with CXXRTL runtime headers; see reference/toolchain.json')
    compiler=shutil.which(os.environ.get('CXX','clang++')) or shutil.which('g++')
    if not compiler:raise SystemExit('C++17 compiler required')
    script='read_verilog -sv rtl/*.sv; hierarchy -check -top tpc_accelerator; proc; opt; memory_collect; check -assert; write_cxxrtl -noflatten -O2 -g0 -header build/accelerator.cc'
    with open('reports/cxxrtl_generation.log','w') as log:
        r=subprocess.run([sys.executable,'scripts/yosys_driver.py',script],stdout=log,stderr=subprocess.STDOUT)
    if r.returncode:raise SystemExit('RTL generation failed; see reports/cxxrtl_generation.log')
    include=Path(pyosys.__file__).parent/'share/include/backends/cxxrtl/runtime'
    if not include.exists():raise SystemExit(f'CXXRTL runtime headers missing at {include}')
    cmd=[compiler,'-std=c++17',os.environ.get('CXXRTL_OPT','-O1'),'-g0','-DNDEBUG',
         '-Wno-shift-count-overflow','-Wno-array-bounds','-shared','-fPIC',f'-I{include}',
         'sim/cxxrtl_driver.cpp','-o','build/libtpc_rtl.so.tmp']
    start=time.time()
    with open('reports/cxxrtl_compile.log','w') as log:
        log.write(' '.join(cmd)+'\n');log.flush()
        r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
    if r.returncode:raise SystemExit('CXXRTL compilation failed; see reports/cxxrtl_compile.log')
    os.replace('build/libtpc_rtl.so.tmp','build/libtpc_rtl.so')
    files=sorted(Path('rtl').glob('*.sv'))+[Path('sim/cxxrtl_driver.cpp')]
    manifest={'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
      'library_sha256':hashlib.sha256(Path('build/libtpc_rtl.so').read_bytes()).hexdigest(),
      'pyosys_version':importlib.metadata.version('pyosys'),'compiler_command':cmd,
      'compile_seconds':time.time()-start,'backend':'ACTUAL_YOSYS_CXXRTL'}
    Path('build/rtl_build_manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Actual RTL library compiled and bound to source hashes')
if __name__=='__main__':main()
