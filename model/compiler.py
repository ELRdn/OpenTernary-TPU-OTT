"""Host-side tiler/exporter for the implemented tile command, not a complete LLM compiler.

All K tiles of a row MUST retain the same output unit. INT64 partials are combined
before any final INT32 saturation. Rotation recipes require an explicit contract.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
import json
import numpy as np
from .numeric import convert_scales,fixed_gemm,rne_shift

@dataclass(frozen=True)
class Tile:
    sequence:int
    token_start:int
    row_start:int
    k_start:int
    tokens:int
    rows:int
    k:int
    bank:int
    tag:int

@dataclass
class LayerPlan:
    a:np.ndarray
    q:np.ndarray
    scales:np.ndarray
    mantissas:np.ndarray
    shifts:np.ndarray
    units:np.ndarray
    coefficient_errors:np.ndarray
    tiles:list[Tile]
    metadata:dict


def plan_layer(a,q,scales,metadata=None)->LayerPlan:
    metadata=dict(metadata or {})
    a=np.asarray(a);q=np.asarray(q);scales=np.asarray(scales,dtype=np.float64)
    if a.dtype!=np.int8 or q.dtype!=np.int8 or a.ndim!=2 or q.ndim!=2:
        raise ValueError('INT8 A[B,K] and Q[R,K] required')
    if min(*a.shape,*q.shape)<1 or a.shape[1]!=q.shape[1] or not np.isin(q,[-1,0,1]).all():
        raise ValueError('invalid dimensions or ternary weight domain')
    if scales.shape!=(q.shape[0],(q.shape[1]+127)//128):
        raise ValueError('scale shape must match last-dim-rowwise G128')
    if metadata.get('group_size',128)!=128 or metadata.get('group_scheme','last-dim-rowwise-v1')!='last-dim-rowwise-v1':
        raise ValueError('unsupported group recipe; no implicit regrouping')
    if metadata.get('activation_transform_required',False) and not metadata.get('activation_transform_applied',False):
        raise ValueError('required activation rotation/transform has not been applied')
    m,s,u,error,underflows=convert_scales(scales)
    if underflows:
        raise ValueError(f'{underflows} coefficient underflows; choose a supported output domain explicitly')
    tiles=[]
    # A-stationary across output rows; W must be reloaded for each 4-token chunk.
    for b in range(0,a.shape[0],4):
        for k in range(0,a.shape[1],4096):
            for r in range(0,q.shape[0],16):
                n=len(tiles)
                tiles.append(Tile(n,b,r,k,min(4,a.shape[0]-b),min(16,q.shape[0]-r),
                                  min(4096,a.shape[1]-k),n%2,n%65536))
    return LayerPlan(a,q,scales,m,s,u,error,tiles,metadata)


def tile_operands(plan:LayerPlan,tile:Tile):
    b,r,k=tile.token_start,tile.row_start,tile.k_start
    g=k//128;ng=(tile.k+127)//128
    return (np.ascontiguousarray(plan.a[b:b+tile.tokens,k:k+tile.k]),
            np.ascontiguousarray(plan.q[r:r+tile.rows,k:k+tile.k]),
            np.ascontiguousarray(plan.mantissas[r:r+tile.rows,g:g+ng]),
            np.ascontiguousarray(plan.shifts[r:r+tile.rows,g:g+ng]))


def execute_plan(plan:LayerPlan,*,rtl=False):
    result=np.zeros((plan.a.shape[0],plan.q.shape[0]),dtype=np.int64)
    dut=None
    if rtl:
        from sim.rtl import RTL
        dut=RTL()
    try:
        for tile in plan.tiles:
            a,q,m,s=tile_operands(plan,tile)
            if dut is None:
                value=fixed_gemm(a,q,m,s)
            else:
                # Diagnostic transport reloads A. A production DMA schedule can reuse it.
                dut.load(a,q,m,s,tile.bank)
                out,_=dut.run(tile.k,tile.rows,tile.tokens,tile.bank,tile.tag)
                if out['flags']&32:raise RuntimeError('hardware numeric/encoding error')
                value=out['data'][:tile.tokens,:tile.rows]
            view=result[tile.token_start:tile.token_start+tile.tokens,tile.row_start:tile.row_start+tile.rows]
            # Guard against overflow before NumPy performs a wrapping addition.
            summed=view.astype(object)+value.astype(object)
            if any(not -(1<<63)<=v<(1<<63) for v in summed.flat):raise OverflowError('INT64 layer accumulation')
            view[:]=summed.astype(np.int64)
    finally:
        if dut is not None:dut.close()
    return result


def full_layer_golden(plan:LayerPlan):
    """Independent group loop; no 4096/16/4 tiling."""
    out=np.zeros((len(plan.a),len(plan.q)),dtype=np.int64)
    for g,k in enumerate(range(0,plan.q.shape[1],128)):
        dots=plan.a[:,k:k+128].astype(np.int64)@plan.q[:,k:k+128].astype(np.int64).T
        for b,r in np.ndindex(out.shape):
            out[b,r]+=rne_shift(int(dots[b,r])*int(plan.mantissas[r,g]),int(plan.shifts[r,g]))
    return out


def export_plan(plan:LayerPlan,folder:Path):
    """Bus images for reproducible RTL loading; this is not an FPGA bitstream."""
    from sim.rtl import RTL
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    manifest={'format':'tpc-x1-bus-images-v1','source_weight_format':'OpenTernary 2bit-v1',
              'group_size':128,'group_scheme':'last-dim-rowwise-v1',
              'shape':{'B':len(plan.a),'R':len(plan.q),'K':plan.q.shape[1]},
              'coefficient_format':'u16 mantissa + u8 shift + reserved-u8=0',
              'output_units':plan.units.tolist(),'metadata':plan.metadata,'tiles':[]}
    for tile in plan.tiles:
        directory=folder/f'tile_{tile.sequence:05d}';directory.mkdir(exist_ok=True)
        a,w,s=RTL.images(*tile_operands(plan,tile))
        for name,words in [('a',a),('w',w),('scale',s)]:
            # One complete 512-bit word/line, as conventional $readmemh hex text.
            (directory/f'{name}.hex').write_text(''.join(''.join(f'{int(x):08x}' for x in row[::-1])+'\n' for row in words))
        manifest['tiles'].append(asdict(tile))
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
    return manifest
