"""Cycle-level specification of the streaming tensor engine.

This models pipeline registers/backpressure; it does NOT execute SystemVerilog.
Cycle counts exclude DDR, DMA and the scratchpad command frontend.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
import numpy as np
from .numeric import rne_shift

@dataclass
class Beat:
    a: np.ndarray
    q: np.ndarray
    keep: np.ndarray
    rows: np.ndarray
    batch: np.ndarray
    first: bool
    last: bool
    tile_first: bool
    tile_last: bool
    tag: int
    m: np.ndarray
    shift: np.ndarray

@dataclass
class Group:
    sums: np.ndarray
    error: bool
    meta: Beat

class MAC:
    def __init__(self, rows=16, lanes=16, batch=4):
        if min(rows,lanes,batch)<1 or lanes&(lanes-1):
            raise ValueError("positive power-of-two LANES required")
        self.rows,self.lanes,self.batch=rows,lanes,batch
        self.depth=lanes.bit_length()
        self.reset()

    def reset(self):
        self.pipe=[None]*self.depth
        self.acc=np.zeros((self.batch,self.rows),dtype=np.int64)
        self.open=False
        self.error=False
        self.out=None
        self.cycles=0

    def ready(self,out_ready):
        return self.out is None or out_ready

    def partial(self,beat):
        if beat.a.shape!=(self.batch,self.lanes) or beat.q.shape!=(self.rows,self.lanes):
            raise ValueError("beat shape mismatch")
        active=beat.rows[:,None]&beat.keep[None,:]
        invalid=bool(np.any(((beat.q<-1)|(beat.q>1))&active)) and bool(beat.batch.any())
        a=beat.a.astype(np.int64)[:,None,:]
        q=beat.q[None,:,:]
        p=np.where(q==1,a,np.where(q==-1,-a,0))
        p=np.where(active[None,:,:]&beat.batch[:,None,None],p,0)
        while p.shape[-1]>1:
            p=p[...,0::2]+p[...,1::2]
        return p[...,0],beat,invalid

    def tick(self,beat,out_ready):
        old=self.out
        accepted=beat is not None and self.ready(out_ready)
        if self.ready(out_ready):
            self.out=None
            tail=self.pipe[-1]
            self.pipe=[self.partial(beat) if accepted else None]+self.pipe[:-1]
            if tail is not None:
                partial,meta,bad=tail
                bad |= (meta.first and self.open) or (not meta.first and not self.open)
                value=partial if meta.first else self.acc+partial
                self.error=(False if meta.first else self.error) or bad
                self.acc=value
                self.open=not meta.last
                if meta.last:
                    self.out=Group(value.copy(),self.error,meta)
        self.cycles+=1
        return accepted,old if old is not None and out_ready else None

class Scaler:
    def __init__(self,rows,batch,group=128):
        self.rows,self.batch,self.group=rows,batch,group
        self.reset()
    def reset(self):
        self.pipe=[None,None]
        self.acc=np.zeros((self.batch,self.rows),dtype=np.int64)
        self.out=None
        self.error=False
    def ready(self,out_ready):
        return self.out is None or out_ready
    def tick(self,group,out_ready):
        old=self.out
        if self.ready(out_ready):
            self.out=None
            tail=self.pipe[-1]
            self.pipe=[group,self.pipe[0]]
            if tail is not None:
                meta=tail.meta
                value=np.zeros_like(tail.sums)
                bad=tail.error or bool(np.any(np.abs(tail.sums)>128*self.group))
                for b,r in np.ndindex(value.shape):
                    shift=int(meta.shift[r])
                    if shift>31 or shift<0:
                        bad=True
                    else:
                        value[b,r]=rne_shift(int(tail.sums[b,r])*int(meta.m[r]),shift)
                self.acc=value if meta.tile_first else self.acc+value
                self.error=(False if meta.tile_first else self.error) or bad
                if meta.tile_last:
                    self.out=(self.acc.copy(),self.error,meta.tag)
        return old if old is not None and out_ready else None

class Engine:
    def __init__(self,rows=16,lanes=16,batch=4,group=128):
        self.mac=MAC(rows,lanes,batch)
        self.scaler=Scaler(rows,batch,group)
        self.reset()
    def reset(self):
        self.mac.reset();self.scaler.reset()
        self.metadata_count=0
        self.metadata=[]
        self.cycles=self.accepted=self.results=0
    def tick(self,beat,out_ready=True):
        sr=self.scaler.ready(out_ready)
        old_group=self.mac.out
        meta_valid=self.metadata_count>0
        pop=old_group is not None and sr and meta_valid
        allow=beat is None or not beat.first or self.metadata_count<4
        bound_group=None
        if pop:
            first_meta=self.metadata[0]
            bound_meta=replace(old_group.meta,m=first_meta.m,shift=first_meta.shift,
                               tile_first=first_meta.tile_first,tile_last=first_meta.tile_last)
            bound_group=Group(old_group.sums,old_group.error,bound_meta)
        result=self.scaler.tick(bound_group,out_ready)
        accepted,_=self.mac.tick(beat if allow else None,sr and meta_valid)
        if accepted and beat.first:
            self.metadata_count+=1
            self.metadata.append(beat)
        if pop:
            self.metadata_count-=1
            self.metadata.pop(0)
        assert 0<=self.metadata_count<=4
        self.cycles+=1;self.accepted+=accepted;self.results+=result is not None
        return accepted,result


def beats(a,q,m,shift,rows=16,lanes=16,batch=4,group=128,tag=0):
    if not 0<a.shape[0]<=batch or not 0<q.shape[0]<=rows or a.shape[1]!=q.shape[1] or not q.shape[1]:
        raise ValueError("bad tile dimensions")
    if group%lanes:
        raise ValueError("GROUP must be divisible by LANES")
    total=q.shape[1]
    for k in range(0,total,lanes):
        n=min(lanes,total-k);g=k//group
        aa=np.zeros((batch,lanes),dtype=np.int8)
        qq=np.zeros((rows,lanes),dtype=np.int8)
        aa[:a.shape[0],:n]=a[:,k:k+n]
        qq[:q.shape[0],:n]=q[:,k:k+n]
        mm=np.zeros(rows,dtype=np.uint16);ss=np.zeros(rows,dtype=np.uint8)
        mm[:q.shape[0]]=m[:,g];ss[:q.shape[0]]=shift[:,g]
        yield Beat(aa,qq,np.arange(lanes)<n,np.arange(rows)<q.shape[0],np.arange(batch)<a.shape[0],
                   k%group==0,(k+n)%group==0 or k+n==total,g==0,g==(total-1)//group,tag,mm,ss)
