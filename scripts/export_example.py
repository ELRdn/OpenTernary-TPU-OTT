from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from model.compiler import plan_layer,export_plan,execute_plan
root=Path(__file__).resolve().parents[1]
rng=np.random.default_rng(20260920)
a=rng.integers(-128,128,(4,257),dtype=np.int8)
q=rng.integers(-1,2,(19,257),dtype=np.int8)
scales=(10**rng.uniform(-4,-1,(19,3))).astype(np.float32)
plan=plan_layer(a,q,scales,{'synthetic':True,'not_a_trained_model':True})
export_plan(plan,root/'examples/bus_images')
np.savez_compressed(root/'examples/synthetic_layer.npz',a=a,q=q,scales=scales,expected=execute_plan(plan))
