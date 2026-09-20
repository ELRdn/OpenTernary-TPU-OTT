"""Driver for actual Yosys/CXXRTL-compiled tpc_accelerator SystemVerilog.
The driver moves bus words only; expected arithmetic comes from model.numeric.
"""
from __future__ import annotations
import ctypes
import hashlib
import json
from pathlib import Path
import numpy as np
from model.packing import pack_2bit
ROOT=Path(__file__).resolve().parents[1]

class RTL:
    def __init__(self):
        library = ROOT / 'build/libtpc_rtl.so'
        manifest_path = ROOT / 'build/rtl_build_manifest.json'
        if not manifest_path.is_file() or not library.is_file():
            raise RuntimeError('Missing actual RTL build or manifest; run scripts/build_cxxrtl.py')
        manifest = json.loads(manifest_path.read_text())
        current_sources = {str(p.relative_to(ROOT)) for p in (ROOT/'rtl').glob('*.sv')}
        current_sources.add('sim/cxxrtl_driver.cpp')
        expected_hashes = manifest.get('source_hashes', {})
        if set(expected_hashes) != current_sources:
            raise RuntimeError('RTL source set differs from the compiled model; rebuild required')
        for name, expected in expected_hashes.items():
            actual = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            if actual != expected:
                raise RuntimeError(f'Stale RTL model: source hash mismatch for {name}; rebuild required')
        if hashlib.sha256(library.read_bytes()).hexdigest() != manifest.get('library_sha256'):
            raise RuntimeError('RTL binary hash mismatch; rebuild required')
        self.lib=ctypes.CDLL(str(library))
        arr=np.ctypeslib.ndpointer(np.uint32,flags='C_CONTIGUOUS')
        self.lib.tpc_rtl_new.restype=ctypes.c_void_p
        self.lib.tpc_rtl_tick.argtypes=[ctypes.c_void_p,arr,arr]
        self.lib.tpc_rtl_tick.restype=ctypes.c_int
        self.lib.tpc_rtl_delete.argtypes=[ctypes.c_void_p]
        self.handle=self.lib.tpc_rtl_new()
        if not self.handle:raise MemoryError('DUT allocation failed')
        self.cycles=0
        self.reset()
    def close(self):
        if self.handle:self.lib.tpc_rtl_delete(self.handle);self.handle=None
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def tick(self,flags=32,a_addr=0,w_addr=0,s_addr=0,k=0,rows=0,batch=0,tag=0,a=None,w=None,s=None):
        inp=np.zeros(56,dtype=np.uint32);out=np.zeros(132,dtype=np.uint32)
        inp[:8]=flags,a_addr,w_addr,s_addr,k,rows,batch,tag
        if a is not None:inp[8:24]=a
        if w is not None:inp[24:40]=w
        if s is not None:inp[40:56]=s
        if self.lib.tpc_rtl_tick(self.handle,inp,out):raise RuntimeError('RTL tick failed')
        self.cycles+=1
        return dict(flags=int(out[0]),post=int(out[1]),tag=int(out[2]),data=out[4:].view(np.int64).reshape(4,16).copy())
    def reset(self):
        for _ in range(3):self.tick(flags=33)
        self.tick()
    @staticmethod
    def images(a,q,m,s):
        k=q.shape[1];blocks=(k+15)//16;groups=(k+127)//128
        aa=[];ww=[];ss=[]
        for i in range(blocks):
            count=min(16,k-i*16)
            av=np.zeros((4,16),dtype=np.int8);qv=np.zeros((16,16),dtype=np.int8)
            av[:len(a),:count]=a[:,i*16:i*16+count]
            qv[:len(q),:count]=q[:,i*16:i*16+count]
            aa.append(np.frombuffer(av.tobytes(),dtype='<u4').copy())
            ww.append(np.frombuffer(pack_2bit(qv.reshape(-1)),dtype='<u4').copy())
        for g in range(groups):
            scale=np.zeros(16,dtype=np.uint32)
            scale[:len(q)]=m[:,g].astype(np.uint32)|(s[:,g].astype(np.uint32)<<16)
            ss.append(scale)
        return aa,ww,ss
    def load(self,a,q,m,s,bank=0):
        aa,ww,ss=self.images(a,q,m,s)
        for i in range(len(aa)):
            flags=32|2|4|(64 if bank else 0)
            if i<len(ss):flags|=8|(128 if bank else 0)
            out=self.tick(flags,a_addr=i,w_addr=i,s_addr=i if i<len(ss) else 0,
                          a=aa[i],w=ww[i],s=ss[i] if i<len(ss) else None)
            assert out['flags']&3==3
            if i<len(ss):assert out['flags']&4
    def run(self,k,rows,batch,bank=0,tag=0,rng=None,max_cycles=10000):
        out=self.tick(32|16|(256 if bank else 0),k=k,rows=rows,batch=batch,tag=tag)
        if not out['flags']&8:raise RuntimeError('command not accepted')
        if out['post']&2:raise RuntimeError(f"rejected command status={out['post']>>8}")
        held=None
        for elapsed in range(1,max_cycles+1):
            ready=rng is None or rng.random()>.3
            out=self.tick(32 if ready else 0)
            if out['flags']&16:
                if held is not None:np.testing.assert_array_equal(out['data'],held)
                if ready:
                    assert out['post']&2
                    return out,elapsed
                held=out['data']
        raise TimeoutError('RTL watchdog')
