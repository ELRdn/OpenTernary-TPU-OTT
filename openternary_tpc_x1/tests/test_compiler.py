import json
import numpy as np
import pytest
from model.compiler import plan_layer,execute_plan,full_layer_golden,export_plan

def test_tiling_preserves_global_row_domain_and_no_early_saturation():
    rng=np.random.default_rng(955)
    a=rng.integers(-128,128,(5,4225),dtype=np.int8)
    q=rng.integers(-1,2,(19,4225),dtype=np.int8)
    scales=(10**rng.uniform(-5,-1,(19,34))).astype(np.float32)
    plan=plan_layer(a,q,scales)
    assert len(plan.tiles)==8
    assert all(t.k_start%128==0 for t in plan.tiles)
    np.testing.assert_array_equal(execute_plan(plan),full_layer_golden(plan))

def test_rotation_contract_is_not_silently_discarded():
    a=np.ones((1,128),dtype=np.int8);q=a.copy();s=np.ones((1,1),dtype=np.float32)
    with pytest.raises(ValueError):plan_layer(a,q,s,{'activation_transform_required':True})
    with pytest.raises(ValueError):plan_layer(a,q,s,{'group_size':64})
    plan_layer(a,q,s,{'activation_transform_required':True,'activation_transform_applied':True})

def test_hardware_export(tmp_path):
    a=np.ones((1,129),dtype=np.int8);q=np.full((17,129),-1,dtype=np.int8)
    plan=plan_layer(a,q,np.ones((17,2),dtype=np.float32))
    manifest=export_plan(plan,tmp_path)
    assert len(manifest['tiles'])==2
    assert len((tmp_path/'tile_00000/w.hex').read_text().splitlines())==9
    assert all(len(x)==128 for x in (tmp_path/'tile_00000/a.hex').read_text().splitlines())
    assert json.loads((tmp_path/'manifest.json').read_text())['shape']['K']==129

def test_tiled_layer_on_actual_rtl():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    if not ((root/'build/libtpc_rtl.so').exists() or (root/'build/libtpc_rtl_optimized.so').exists()):
        pytest.skip('actual RTL library missing')
    rng=np.random.default_rng(956)
    a=rng.integers(-128,128,(5,4225),dtype=np.int8)
    q=rng.integers(-1,2,(19,4225),dtype=np.int8)
    scales=(10**rng.uniform(-4,-1,(19,34))).astype(np.float32)
    plan=plan_layer(a,q,scales)
    np.testing.assert_array_equal(execute_plan(plan,rtl=True),full_layer_golden(plan))
