#!/usr/bin/env python3
"""Reproduce selected stages. Missing required tools never silently count as PASS.

reports/results.json remains the supplied dated snapshot. This command records a
fresh reports/reproduction_run.json and reproduction_pytest.xml for each run.
"""
from pathlib import Path
import argparse, datetime, json, os, subprocess, sys, time
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
p=argparse.ArgumentParser()
p.add_argument('--build-rtl',action='store_true')
p.add_argument('--synth',action='store_true')
p.add_argument('--models-only',action='store_true')
a=p.parse_args()
(ROOT/'reports').mkdir(exist_ok=True)
(ROOT/'build').mkdir(exist_ok=True)
report={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope':'MODELS_ONLY_NOT_RTL' if a.models_only else 'ACTUAL_RTL_AND_MODELS',
        'status':'RUNNING','stages':[],'original_snapshot':'reports/results.json'}
report_path=ROOT/'reports/reproduction_run.json'
def save(): report_path.write_text(json.dumps(report,indent=2))
def run(cmd):
    print('+',' '.join(cmd),flush=True)
    stage={'command':cmd,'status':'RUNNING'}
    report['stages'].append(stage);save();start=time.monotonic()
    result=subprocess.run(cmd)
    stage.update(exit_code=result.returncode,seconds=time.monotonic()-start,
                 status='PASS' if result.returncode==0 else 'FAIL')
    save()
    if result.returncode: raise subprocess.CalledProcessError(result.returncode,cmd)
save()
try:
    run(['g++','-std=c++17','-O2','-shared','-fPIC','model/reference.cpp','-o','build/libtpc_reference.so'])
    if a.build_rtl:run([sys.executable,'scripts/build_cxxrtl.py'])
    if not a.models_only:
        if not (ROOT/'build/libtpc_rtl.so').exists():
            raise RuntimeError('Missing actual RTL library; use --build-rtl or explicitly --models-only')
        run([sys.executable,'scripts/formal_checks.py'])
        run([sys.executable,'scripts/check_hot_path.py'])
    targets=['tests/test_numeric.py','tests/test_cycle.py'] if a.models_only else ['tests']
    run([sys.executable,'-m','pytest',*targets,'-q','--junitxml=reports/reproduction_pytest.xml'])
    suites=ET.parse(ROOT/'reports/reproduction_pytest.xml').getroot()
    totals={key:sum(int(s.attrib.get(key,'0')) for s in suites.iter('testsuite'))
            for key in ('tests','failures','errors','skipped')}
    report['tests']=totals
    if not a.models_only and totals['skipped']:
        raise RuntimeError('Full reproduction contains skipped tests; not accepted as complete')
    if a.synth:run([sys.executable,'scripts/synth_xcup.py'])
    if not a.models_only:run([sys.executable,'scripts/analyze_performance.py'])
    report['status']='PASS'
except Exception as exc:
    report['status']='FAIL';report['error']=repr(exc);save()
    raise
finally:
    report['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
