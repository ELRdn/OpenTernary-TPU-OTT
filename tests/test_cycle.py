from dataclasses import replace
import numpy as np
from model.cycle import Engine,MAC,beats
from model.numeric import fixed_gemm


def execute(engine,source,rng,bubbles=True):
    source=iter(source);held=None;done=False;outputs=[];count=0
    for cycle in range(200000):
        if held is None and not done and (not bubbles or rng.random()>.12):
            try:held=next(source)
            except StopIteration:done=True
        ready=not bubbles or rng.random()>.25
        before=engine.scaler.out
        accepted,result=engine.tick(held,ready)
        if before is not None and not ready:
            assert engine.scaler.out is before
        if accepted:held=None;count+=1
        if result is not None:outputs.append(result)
        if done and held is None and engine.metadata_count==0 and engine.mac.out is None \
           and not any(x is not None for x in engine.mac.pipe) \
           and not any(x is not None for x in engine.scaler.pipe) and engine.scaler.out is None:
            return outputs,count,cycle+1
    raise AssertionError('watchdog: pipeline failed to drain')


def test_10000_random_tile_transactions():
    rng=np.random.default_rng(7720920)
    engine=Engine(4,8,2,128)
    for tag in range(10000):
        b=int(rng.integers(1,3));r=int(rng.integers(1,5));k=int(rng.integers(1,258));g=(k+127)//128
        a=rng.integers(-128,128,(b,k),dtype=np.int8);q=rng.integers(-1,2,(r,k),dtype=np.int8)
        m=rng.integers(0,65536,(r,g),dtype=np.uint16);s=rng.integers(0,32,(r,g),dtype=np.uint8)
        stream=list(beats(a,q,m,s,rows=4,lanes=8,batch=2,tag=tag))
        # Deliberately invalid masked padding must not poison a valid result.
        for beat in stream:
            beat.q[:,~beat.keep]=2
        results,accepted,_=execute(engine,stream,rng)
        assert accepted==(k+7)//8 and len(results)==1
        out,error,outtag=results[0]
        gold=np.zeros((2,4),dtype=np.int64);gold[:b,:r]=fixed_gemm(a,q,m,s)
        assert not error and outtag==tag
        np.testing.assert_array_equal(out,gold)


def test_full_16x16x4_candidate():
    rng=np.random.default_rng(7654)
    for k in [1,15,16,17,127,128,129,1023,1024,4095,4096]:
        for b in [1,4]:
            engine=Engine()
            a=rng.integers(-128,128,(b,k),dtype=np.int8);q=rng.integers(-1,2,(16,k),dtype=np.int8)
            m=rng.integers(1,65536,(16,(k+127)//128),dtype=np.uint16)
            s=rng.integers(0,32,m.shape,dtype=np.uint8)
            results,_,_=execute(engine,beats(a,q,m,s),rng)
            gold=np.zeros((4,16),dtype=np.int64);gold[:b]=fixed_gemm(a,q,m,s)
            assert len(results)==1 and not results[0][1]
            np.testing.assert_array_equal(results[0][0],gold)


def test_metadata_fifo_backpressure_and_first_capture():
    rng=np.random.default_rng(55);engine=Engine(4,8,2)
    all_beats=[];expected=[]
    for tag in range(200):
        a=np.full((2,1),tag%127,dtype=np.int8);q=np.ones((4,1),dtype=np.int8)
        m=np.full((4,1),tag+1,dtype=np.uint16);s=np.zeros((4,1),dtype=np.uint8)
        all_beats.extend(beats(a,q,m,s,rows=4,lanes=8,batch=2,tag=tag))
        expected.append(fixed_gemm(a,q,m,s))
    results,count,_=execute(engine,all_beats,rng)
    assert count==200 and len(results)==200
    for i,result in enumerate(results):
        assert result[2]==i and not result[1]
        np.testing.assert_array_equal(result[0],expected[i])
    # A group's coefficients are captured on FIRST, not its final beat.
    a=np.ones((2,16),dtype=np.int8);q=np.ones((4,16),dtype=np.int8)
    m=np.full((4,1),7,dtype=np.uint16);s=np.zeros((4,1),dtype=np.uint8)
    stream=list(beats(a,q,m,s,rows=4,lanes=8,batch=2))
    stream[-1]=replace(stream[-1],m=np.full(4,999,dtype=np.uint16))
    out,_,_=execute(engine,stream,rng)
    np.testing.assert_array_equal(out[0][0],np.full((2,4),16*7))


def test_reset_and_invalid_active_code():
    rng=np.random.default_rng(21);engine=Engine(4,8,2)
    a=np.full((2,16),-128,dtype=np.int8);q=np.full((4,16),-1,dtype=np.int8)
    m=np.ones((4,1),dtype=np.uint16);s=np.zeros((4,1),dtype=np.uint8)
    stream=list(beats(a,q,m,s,rows=4,lanes=8,batch=2))
    engine.tick(stream[0]);engine.reset()
    out,_,_=execute(engine,[],rng)
    assert out==[]
    stream[0].q[0,0]=2
    out,_,_=execute(engine,stream,rng)
    assert out[0][1]
    stream=list(beats(a,q,m,s,rows=4,lanes=8,batch=2))
    out,_,_=execute(engine,stream,rng)
    assert not out[0][1] and np.all(out[0][0]==2048)


def test_mac_protocol_error():
    a=np.ones((2,1),dtype=np.int8);q=np.ones((4,1),dtype=np.int8)
    beat=next(beats(a,q,np.ones((4,1),dtype=np.uint16),np.zeros((4,1),dtype=np.uint8),rows=4,lanes=8,batch=2))
    beat=replace(beat,first=False)
    mac=MAC(4,8,2);mac.tick(beat,True)
    result=None
    for _ in range(20):
        _,got=mac.tick(None,True)
        if got is not None:result=got
    assert result is not None and result.error
