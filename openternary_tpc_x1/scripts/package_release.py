#!/usr/bin/env python3
"""Package task artifacts only; verify ZIP CRCs and every manifest hash."""
from pathlib import Path
import hashlib, json, zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'OpenTernary_TPC_X1_20260920.zip'
EXCLUDE={
    'build/libtpc_rtl_optimized.so',
    'build/accelerator_flat.cc',
    'reports/final_reproduction_timeout.log',
    'reports/final_rtl_pytest.log',
}
def eligible(path):
    rel=path.relative_to(ROOT)
    return (path.is_file() and not any(x in {'__pycache__','.pytest_cache','.git'} for x in rel.parts)
            and path.suffix not in {'.pyc','.pyo','.tmp'} and str(rel) not in EXCLUDE
            and str(rel) not in {'MANIFEST.sha256','package_inventory.json'})
status=json.loads((ROOT/'reports/reproduction_run.json').read_text())
if status.get('status')!='PASS' or status.get('tests')!={'tests':24,'failures':0,'errors':0,'skipped':0}:
    raise SystemExit('Latest full reproduction is not a clean 24-test PASS')
files=sorted(p for p in ROOT.rglob('*') if eligible(p))
assert not any(p.suffix.lower() in {'.ttf','.otf','.woff','.woff2'} for p in files)
inventory={
    'release':'OpenTernary TPC-X1 2026-09-20',
    'scope':'TILE_RTL_VERIFIED; FULL_LLM_COMPETITIVE_PERFORMANCE_UNMEASURED',
    'payload_files_excluding_inventory_and_manifest':len(files),
    'payload_bytes_excluding_inventory_and_manifest':sum(p.stat().st_size for p in files),
    'excluded':'toolchain packages, unrelated uploads, caches, duplicate build binary, interrupted audit attempts',
    'files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,
              'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
}
(ROOT/'package_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2))
files.append(ROOT/'package_inventory.json');files.sort()
manifest=''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT)}\n' for p in files)
(ROOT/'MANIFEST.sha256').write_text(manifest)
files.append(ROOT/'MANIFEST.sha256');files.sort()
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in files:z.write(p,arcname=f'{ROOT.name}/{p.relative_to(ROOT)}')
with zipfile.ZipFile(OUT) as z:
    assert z.testzip() is None,'ZIP CRC failure'
    for line in manifest.splitlines():
        expected,name=line.split('  ',1)
        assert hashlib.sha256(z.read(f'{ROOT.name}/{name}')).hexdigest()==expected,name
    names=set(z.namelist())
    for req in ['README.md','REPORT.html','REPORT.md','rtl/tpc_accelerator.sv','reports/results.json','reports/reproduction_run.json']:
        assert f'{ROOT.name}/{req}' in names,req
record={'archive':str(OUT),'files':len(files),'bytes':OUT.stat().st_size,
        'uncompressed_bytes':sum(p.stat().st_size for p in files),
        'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),
        'zip_crc_check':'PASS','all_manifest_hashes':'PASS'}
(ROOT.parent/'TPC_X1_archive_verification.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2))
