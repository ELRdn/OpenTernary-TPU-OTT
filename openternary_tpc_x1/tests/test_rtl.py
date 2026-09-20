"""Tests against actual SystemVerilog compiled by Yosys/CXXRTL.

CXXRTL is a two-state RTL simulator. This is not a Python stand-in for the DUT.
"""
from pathlib import Path
import json
import numpy as np
import pytest
from sim.rtl import RTL
from model.numeric import fixed_gemm

ROOT=Path(__file__).resolve().parents[1]
if not (ROOT/'build/libtpc_rtl.so').is_file():
    pytest.skip('Real compiled RTL library is missing; run scripts/build_cxxrtl.py',allow_module_level=True)


def operands(rng,b,r,k):
    ng=(k+127)//128
    return (rng.integers(-128,128,(b,k),dtype=np.int8),rng.integers(-1,2,(r,k),dtype=np.int8),
            rng.integers(0,65536,(r,ng),dtype=np.uint16),rng.integers(0,32,(r,ng),dtype=np.uint8))


def padded_expected(a,q,m,s):
    gold=np.zeros((4,16),dtype=np.int64)
    gold[:len(a),:len(q)]=fixed_gemm(a,q,m,s)
    return gold


def assert_success(out,gold,tag):
    np.testing.assert_array_equal(out['data'],gold)
    assert not (out['flags']&32), 'out_error asserted'
    assert out['post']>>8==0
    assert out['tag']==tag


def test_rtl_random_1000_full_top():
    rng=np.random.default_rng(2026092081)
    sizes=[1,2,3,15,16,17,31,63,64,127,128,129,255,256,257,511,512]
    total_terms=0;cycles=0;max_cycles=0
    with RTL() as dut:
        for index in range(1000):
            k=(4095 if index==0 else 4096) if index<2 else int(rng.choice(sizes))
            b=int(rng.integers(1,5));r=int(rng.integers(1,17))
            a,q,m,s=operands(rng,b,r,k)
            if index%41==0: a[:]=-128
            if index%43==0: q[:]=-1
            if index%47==0: q[:]=0
            if index%53==0: m[:]=65535;s[:]=0
            bank=index%2
            dut.load(a,q,m,s,bank)
            result,elapsed=dut.run(k,r,b,bank,index,rng)
            assert_success(result,padded_expected(a,q,m,s),index)
            total_terms+=b*r*k;cycles+=elapsed;max_cycles=max(max_cycles,elapsed)
        report={'kind':'ACTUAL_YOSYS_CXXRTL_SYSTEMVERILOG','seed':2026092081,
                'randomized_commands':1000,'output_values_checked':64000,
                'active_ternary_products_checked':total_terms,
                'command_to_consume_cycles_sum':cycles,'max_command_cycles':max_cycles,
                'all_bus_cycles_including_load_reset':dut.cycles,
                'output_backpressure':True,'both_weight_banks':True,
                'four_state_x_propagation':False,'fpga_hardware_measured':False}
    (ROOT/'reports/rtl_coverage.json').write_text(json.dumps(report,indent=2))


def test_rtl_full_width_boundaries_and_cycle_formula():
    records=[]
    with RTL() as dut:
        for b in (1,4):
            for k in [1,16,17,127,128,129,255,256,257,4095,4096]:
                a=np.full((b,k),-128,dtype=np.int8);q=np.full((16,k),-1,dtype=np.int8)
                m=np.full((16,(k+127)//128),65535,dtype=np.uint16)
                s=np.zeros_like(m,dtype=np.uint8)
                dut.load(a,q,m,s)
                out,cycles=dut.run(k,16,b,tag=k)
                assert_success(out,padded_expected(a,q,m,s),k)
                assert cycles==(k+15)//16+10
                records.append({'B':b,'R':16,'K':k,'cycles':cycles,
                                'input_beats':(k+15)//16,'active_terms':b*16*k})
    (ROOT/'reports/rtl_cycle_measurements.json').write_text(json.dumps({
        'source':'ACTUAL_CXXRTL', 'excludes_loading':True,'clock_frequency_measured':False,
        'records':records},indent=2))


def test_rtl_bad_commands_and_uninitialized_memory():
    with RTL() as dut:
        for k,r,b in [(0,1,1),(4097,1,1),(1,0,1),(1,17,1),(1,1,0),(1,1,5)]:
            out=dut.tick(32|16,k=k,rows=r,batch=b)
            assert out['flags']&8
            assert out['post']&2 and not out['post']&1
            assert out['post']>>8==1
        out=dut.tick(32|16,k=128,rows=1,batch=1)
        assert out['post']&2 and out['post']>>8==2
        assert not out['flags']&16


def test_rtl_bad_weight_masked_tail_and_bad_scale():
    with RTL() as dut:
        a=np.array([[-128]],dtype=np.int8);q=np.array([[-1]],dtype=np.int8)
        m=np.array([[1]],dtype=np.uint16);s=np.array([[0]],dtype=np.uint8)
        aa,ww,ss=dut.images(a,q,m,s)
        dut.load(a,q,m,s)
        bad=ww[0].copy();bad[0]=(int(bad[0])&~0xC0)|0xC0
        dut.tick(32|4,w=bad)
        out,_=dut.run(1,1,1)
        assert out['flags']&32 and out['post']>>8==3
        # Lane1 is outside logical K; its 11 code must be ignored.
        padded=ww[0].copy();padded[0]=(int(padded[0])&~0x30)|0x30
        dut.tick(32|4,w=padded)
        out,_=dut.run(1,1,1)
        assert_success(out,padded_expected(a,q,m,s),0)
        for invalid in (1|(32<<16),1|(1<<24)):
            scale=ss[0].copy();scale[0]=invalid
            dut.tick(32|8,s=scale)
            out,_=dut.run(1,1,1)
            assert out['flags']&32 and out['post']>>8==3


def test_rtl_pingpong_ownership_and_busy_command():
    rng=np.random.default_rng(61);a,q0,m,s=operands(rng,4,16,512)
    q1=-q0
    with RTL() as dut:
        dut.load(a,q0,m,s,0);dut.load(a,q1,m,s,1)
        aa,w1,ss=dut.images(a,q1,m,s)
        start=dut.tick(32|16,k=512,rows=16,batch=4,tag=55)
        assert start['flags']&8 and start['post']&1
        result=None
        for cycle in range(100):
            # Activation and active bank writes must be blocked; commands must be blocked.
            if cycle%2==0:
                out=dut.tick(32|2|4|8|16,a=aa[0],w=w1[0],s=ss[0],k=1,rows=1,batch=1,tag=999)
                assert not out['flags']&1
                assert not out['flags']&2
                assert not out['flags']&4
                assert not out['flags']&8
            else:
                out=dut.tick(32|4|8|64|128,w_addr=0,s_addr=0,w=w1[0],s=ss[0])
                assert out['flags']&2 and out['flags']&4
            if out['flags']&16:
                result=out;break
        assert result is not None
        assert_success(result,padded_expected(a,q0,m,s),55)
        out,_=dut.run(512,16,4,1,56)
        assert_success(out,padded_expected(a,q1,m,s),56)


def test_rtl_reset_drops_inflight_and_validity():
    rng=np.random.default_rng(62);a,q,m,s=operands(rng,4,16,512)
    with RTL() as dut:
        dut.load(a,q,m,s)
        dut.tick(32|16,k=512,rows=16,batch=4,tag=10)
        for _ in range(8):dut.tick()
        dut.reset()
        for _ in range(15):
            out=dut.tick()
            assert not out['flags']&16
            assert not out['post']&1
        out=dut.tick(32|16,k=512,rows=16,batch=4)
        assert out['post']>>8==2
        dut.load(a,q,m,s)
        out,_=dut.run(512,16,4,tag=11)
        assert_success(out,padded_expected(a,q,m,s),11)
