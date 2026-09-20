"""Independent implementation of the OpenTernary 2bit-v1 format and lossless T5.
Canonical reference: ELRdn/OpenTernary commit 31564aeff6b03a46942ef048715058f4b5cba320.
Packing is per tensor; grouping and tiling are separate layout transformations.
"""
from __future__ import annotations
from numbers import Integral
from typing import Iterable


def _values(values: Iterable[int]) -> list[int]:
    out = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, Integral) or value not in (-1, 0, 1):
            raise ValueError(f"invalid ternary integer {value!r}")
        out.append(int(value))
    return out


def pack_2bit(values: Iterable[int]) -> bytes:
    values = _values(values)
    out = bytearray((len(values)+3)//4)
    for i, q in enumerate(values):
        out[i//4] |= (q+1) << (6-2*(i%4))
    return bytes(out)  # unused slots are 00 (-1), not logical zero (01)


def unpack_2bit(data: bytes, count: int, strict: bool = True) -> list[int]:
    if not isinstance(count, Integral) or count < 0 or count > len(data)*4:
        raise ValueError("invalid original element count")
    if strict and len(data) != (count+3)//4:
        raise ValueError("nonminimal byte length")
    out = []
    for i in range(count):
        code = (data[i//4] >> (6-2*(i%4))) & 3
        if code == 3:
            raise ValueError(f"reserved code 11 at element {i}")
        out.append(code-1)
    if strict and count%4 and data[count//4] & ((1 << (2*(4-count%4)))-1):
        raise ValueError("tail padding must be 00")
    return out


def pack_t5(values: Iterable[int]) -> bytes:
    """Five trits/byte; digit q+1; first trit has radix place 3**0.
    No codebook pruning. All 243 combinations are losslessly represented.
    Unused tail digits are zero (masked -1); count is mandatory.
    """
    values = _values(values)
    out = bytearray((len(values)+4)//5)
    for i, q in enumerate(values):
        out[i//5] += (q+1)*3**(i%5)
    return bytes(out)


def unpack_t5(data: bytes, count: int, strict: bool = True) -> list[int]:
    if not isinstance(count, Integral) or count < 0 or count > len(data)*5:
        raise ValueError("invalid count")
    if strict and len(data) != (count+4)//5:
        raise ValueError("nonminimal byte length")
    if any(byte >= 243 for byte in data):
        raise ValueError("invalid T5 byte 243..255")
    if strict and count%5 and data[count//5] >= 3**(count%5):
        raise ValueError("noncanonical T5 tail")
    return [(data[i//5]//3**(i%5))%3-1 for i in range(count)]


def accounting(k: int, group: int = 128, scale_bytes: int = 4) -> dict:
    if k < 0 or group <= 0 or scale_bytes < 0:
        raise ValueError("invalid dimensions")
    lengths = [min(group, k-j) for j in range(0,k,group)]
    w2 = sum((n+3)//4 for n in lengths)
    w5 = sum((n+4)//5 for n in lengths)
    scales = len(lengths)*scale_bytes
    return dict(groups=len(lengths), canonical_tensor_weight_bytes=(k+3)//4,
                grouped_2bit_weight_bytes=w2, t5_weight_bytes=w5, scale_bytes=scales,
                grouped_2bit_total=w2+scales, t5_total=w5+scales,
                t5_effective_bits=(w5+scales)*8/k if k else 0)
