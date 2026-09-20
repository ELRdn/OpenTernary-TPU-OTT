import ctypes
from fractions import Fraction
from pathlib import Path
import itertools
import numpy as np
import pytest
from model.packing import pack_2bit,unpack_2bit,pack_t5,unpack_t5,accounting
from model.numeric import rne_shift,saturate32,coefficient,convert_scales,grouped_dots,fixed_gemm,error_bound

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def lib():
    lib=ctypes.CDLL(str(ROOT/'build/libtpc_reference.so'))
    i8=np.ctypeslib.ndpointer(np.int8,flags='C_CONTIGUOUS')
    u16=np.ctypeslib.ndpointer(np.uint16,flags='C_CONTIGUOUS')
    u8=np.ctypeslib.ndpointer(np.uint8,flags='C_CONTIGUOUS')
    i64=np.ctypeslib.ndpointer(np.int64,flags='C_CONTIGUOUS')
    lib.tpc_gemm.argtypes=[i8,i8,u16,u8,i64]+[ctypes.c_size_t]*4
    lib.tpc_gemm.restype=ctypes.c_int
    lib.tpc_rne.argtypes=[ctypes.c_int64,ctypes.c_uint]
    lib.tpc_rne.restype=ctypes.c_int64
    return lib


def cpp(lib,a,q,m,s,group=128):
    result=np.zeros((len(a),len(q)),dtype=np.int64)
    rc=lib.tpc_gemm(np.ascontiguousarray(a),np.ascontiguousarray(q),np.ascontiguousarray(m),
                    np.ascontiguousarray(s),result,len(a),len(q),q.shape[1],group)
    assert rc==0
    return result


def test_canonical_known_byte_and_exhaustive():
    assert pack_2bit([-1,0,1,-1])==b'\x18'
    assert pack_2bit([1])==b'\x80'
    for values in itertools.product([-1,0,1],repeat=4):
        assert unpack_2bit(pack_2bit(values),4)==list(values)
    for n in range(256):
        valid=all(((n>>(2*i))&3)!=3 for i in range(4))
        if valid:
            assert pack_2bit(unpack_2bit(bytes([n]),4))==bytes([n])
        else:
            with pytest.raises(ValueError):unpack_2bit(bytes([n]),4)


def test_t5_exhaustive_and_rom_table():
    import re
    rom=(ROOT/'rtl/tpc_radix3_decode5.sv').read_text()
    mappings={int(n):int(v,16) for n,v in re.findall(r"8'd(\d+): codes=10'h([0-9a-f]+)",rom)}
    assert len(mappings)==243
    seen=set()
    for values in itertools.product([-1,0,1],repeat=5):
        packed=pack_t5(values);seen.add(packed)
        assert unpack_t5(packed,5)==list(values)
        expected=sum((v+1)<<(2*i) for i,v in enumerate(values))
        assert mappings[packed[0]]==expected
    assert len(seen)==243
    for n in range(243,256):
        with pytest.raises(ValueError):unpack_t5(bytes([n]),5)


def test_tails_lengths_and_random_roundtrip():
    rng=np.random.default_rng(20260920)
    for n in list(range(130))+[255,256,257,1023,1024,4095,4096]:
        v=rng.integers(-1,2,n,dtype=np.int8)
        assert unpack_2bit(pack_2bit(v),n)==v.tolist()
        assert unpack_t5(pack_t5(v),n)==v.tolist()
    for fun,packed,count in [(unpack_2bit,b'\x81',1),(unpack_t5,b'\x05',1),
                             (unpack_2bit,b'\0',0),(unpack_t5,b'\0',0)]:
        with pytest.raises(ValueError):fun(packed,count)
    for bad in [2,-2,0.0,True,'0']:
        with pytest.raises(ValueError):pack_2bit([bad])
    assert accounting(128)['t5_effective_bits']==1.875
    assert accounting(128)['grouped_2bit_total']==36
    assert accounting(128)['t5_total']==30


def test_all_int8_ternary_products(lib):
    a=np.arange(-128,128,dtype=np.int16).astype(np.int8).reshape(256,1)
    q=np.array([[-1],[0],[1]],dtype=np.int8)
    m=np.ones((3,1),dtype=np.uint16);s=np.zeros((3,1),dtype=np.uint8)
    out=cpp(lib,a,q,m,s)
    np.testing.assert_array_equal(out,a.astype(np.int64)@q.astype(np.int64).T)
    assert out[0,0]==128


def test_rounding_against_exact_fraction_and_cpp(lib):
    rng=np.random.default_rng(7813)
    cases=[(x,s) for x in range(-129,130) for s in range(9)]
    cases += [(int(rng.integers(-(1<<32),1<<32)),int(rng.integers(0,32))) for _ in range(10000)]
    for x,s in cases:
        gold=round(Fraction(x,1<<s))
        assert rne_shift(x,s)==gold
        assert lib.tpc_rne(x,s)==gold
    with pytest.raises(ValueError):rne_shift(1,32)


def test_scale_conversion_error_bound():
    rng=np.random.default_rng(76)
    for _ in range(100):
        a=rng.integers(-128,128,(4,513),dtype=np.int8)
        q=rng.integers(-1,2,(16,513),dtype=np.int8)
        scales=(10.0**rng.uniform(-7,0,(16,5))).astype(np.float32)
        m,s,u,err,under=convert_scales(scales)
        actual=fixed_gemm(a,q,m,s)
        dots=grouped_dots(a,q)
        target=np.sum(dots*(scales.astype(np.float64)/u[:,None])[None,:,:],axis=-1)
        assert np.all(np.abs(actual-target)<=error_bound(dots,err)+1e-7)
        assert under==0
    assert coefficient(1e-40).underflow
    for bad in [-1,float('inf'),float('nan'),65536]:
        with pytest.raises(ValueError):coefficient(bad)


def test_cpp_gemm_random_1500(lib):
    rng=np.random.default_rng(93151)
    sizes=[1,2,3,7,8,15,16,17,63,64,65,127,128,129,255,256,257,511,512,1023,4095,4096]
    for _ in range(1500):
        b=int(rng.integers(1,5));r=int(rng.integers(1,17));k=int(rng.choice(sizes));g=(k+127)//128
        a=rng.integers(-128,128,(b,k),dtype=np.int8)
        q=rng.integers(-1,2,(r,k),dtype=np.int8)
        m=rng.integers(0,65536,(r,g),dtype=np.uint16)
        s=rng.integers(0,32,(r,g),dtype=np.uint8)
        np.testing.assert_array_equal(cpp(lib,a,q,m,s),fixed_gemm(a,q,m,s))


def test_large_accumulator_and_saturation(lib):
    a=np.full((1,4096),-128,dtype=np.int8)
    q=np.full((1,4096),-1,dtype=np.int8)
    m=np.full((1,32),65535,dtype=np.uint16);s=np.zeros((1,32),dtype=np.uint8)
    result=cpp(lib,a,q,m,s)[0,0]
    assert result==4096*128*65535
    assert saturate32(int(result))==((1<<31)-1,True)
    assert saturate32(-int(result))==(-(1<<31),True)


def test_invalid_cpp_inputs(lib):
    a=np.ones((1,1),dtype=np.int8);q=np.array([[2]],dtype=np.int8)
    m=np.ones((1,1),dtype=np.uint16);s=np.zeros((1,1),dtype=np.uint8);out=np.zeros((1,1),dtype=np.int64)
    assert lib.tpc_gemm(a,q,m,s,out,1,1,1,128)==3
    q[0,0]=1;s[0,0]=32
    assert lib.tpc_gemm(a,q,m,s,out,1,1,1,128)==2
