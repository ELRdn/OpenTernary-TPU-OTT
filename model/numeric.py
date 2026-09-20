"""Golden integer arithmetic and a quantified FP32-scale conversion contract."""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np


def rne_shift(value: int, shift: int) -> int:
    if not 0 <= shift <= 31:
        raise ValueError("shift must be 0..31")
    if shift == 0:
        return int(value)
    q,r = divmod(abs(int(value)), 1<<shift)
    half = 1<<(shift-1)
    q += int(r>half or (r==half and q%2==1))
    return -q if value<0 else q


def saturate32(value: int) -> tuple[int,bool]:
    out = max(-(1<<31), min((1<<31)-1, int(value)))
    return out, out != value


@dataclass(frozen=True)
class Coefficient:
    mantissa: int
    shift: int
    absolute_error: float
    underflow: bool

    @property
    def value(self):
        return math.ldexp(float(self.mantissa), -self.shift)


def coefficient(value: float) -> Coefficient:
    if not math.isfinite(value) or not 0 <= value <= 65535:
        raise ValueError("scale ratio must be finite in [0,65535]")
    for shift in range(31,-1,-1):
        m = round(math.ldexp(value,shift))
        if m <= 65535:
            v = math.ldexp(float(m),-shift)
            return Coefficient(m,shift,abs(value-v),value!=0 and m==0)
    raise AssertionError("unreachable")


def convert_scales(scales: np.ndarray, units: np.ndarray | None = None):
    """Per-row common output unit; token activation scales remain outside hardware.
    y_real = y_integer * units[row] * activation_scale[token].
    Coefficient quantization is not identical to FP32 scale multiplication.
    """
    scales = np.asarray(scales, dtype=np.float64)
    if scales.ndim!=2 or scales.shape[1]==0 or not np.isfinite(scales).all() or (scales<0).any():
        raise ValueError("finite nonnegative [rows,groups] scales required")
    if units is None:
        units = np.array([2.0**(math.ceil(math.log2(v))-14) if v else 1.0
                          for v in scales.max(axis=1)], dtype=np.float64)
    units = np.asarray(units, dtype=np.float64)
    if units.shape!=(scales.shape[0],) or not np.isfinite(units).all() or (units<=0).any():
        raise ValueError("invalid output units")
    m = np.zeros(scales.shape, dtype=np.uint16)
    s = np.zeros(scales.shape, dtype=np.uint8)
    error = np.zeros(scales.shape)
    underflows = 0
    for r,g in np.ndindex(scales.shape):
        c = coefficient(float(scales[r,g]/units[r]))
        m[r,g],s[r,g],error[r,g] = c.mantissa,c.shift,c.absolute_error
        underflows += int(c.underflow)
    return m,s,units,error,underflows


def grouped_dots(a: np.ndarray, q: np.ndarray, group: int = 128) -> np.ndarray:
    if a.dtype!=np.int8 or q.dtype!=np.int8 or a.ndim!=2 or q.ndim!=2:
        raise ValueError("INT8 a[B,K], q[R,K] required")
    if a.shape[1]!=q.shape[1] or not a.shape[1] or group<1 or a.shape[1]>4096:
        raise ValueError("invalid dimensions")
    if not np.isin(q,[-1,0,1]).all():
        raise ValueError("nonternary weight")
    # Independent golden: integer matrix multiplication, not sign selection.
    return np.stack([a[:,k:k+group].astype(np.int64) @ q[:,k:k+group].astype(np.int64).T
                     for k in range(0,q.shape[1],group)],axis=-1)


def fixed_gemm(a,q,m,shift,group=128):
    dots = grouped_dots(a,q,group)
    if m.shape!=dots.shape[1:] or shift.shape!=m.shape:
        raise ValueError("scale shape mismatch")
    if (shift>31).any() or (shift<0).any() or (m<0).any() or (m>65535).any():
        raise ValueError("coefficient out of range")
    out = np.zeros(dots.shape[:2],dtype=np.int64)
    for b,r,g in np.ndindex(dots.shape):
        out[b,r] += rne_shift(int(dots[b,r,g])*int(m[r,g]),int(shift[r,g]))
    return out


def error_bound(dots,coefficient_errors):
    return np.sum(np.abs(dots)*coefficient_errors[None,:,:]+0.5,axis=-1)


def quantize_activation(x):
    x = np.asarray(x,dtype=np.float64)
    if x.ndim!=2 or not np.isfinite(x).all():
        raise ValueError("finite [batch,K] activations required")
    maximum = np.max(np.abs(x),axis=-1,keepdims=True)
    scale = np.where(maximum>0,maximum/127.0,1.0)
    return np.clip(np.rint(x/scale),-127,127).astype(np.int8),scale[:,0]
