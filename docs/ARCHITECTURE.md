# OTT / TPC-X1 Architecture

TPC-X1 is the first substantial accelerator architecture under **OpenTernary TPU (OTT)**. It is a tiled ternary GEMV/GEMM engine designed around OpenTernary's packed ternary weights and G128-style scale boundaries.

## Compute organization

The default configuration is **R16 × L16 × B4**:

- `R=16`: output rows processed in parallel
- `L=16`: K-dimension ternary lanes per cycle
- `B=4`: activation/token vectors sharing loaded weights

This gives up to `R × L × B = 1024` ternary products per input cycle when all lanes are active.

## Datapath

```text
packed / decoded ternary weights
              |
INT8 activations +--> ternary sign-select product
                     (+x / 0 / -x)
                              |
                              v
                    lane reduction / group sum
                              |
                         INT32 group sum
                              |
                              v
                        G128 scale unit
                              |
                              v
                    INT64 output accumulation
```

The ternary MAC hot path does not require a conventional multiplier. Multiplication resources currently reported by synthesis are associated with the separate scale path.

## Memory and scheduling

TPC-X1 includes a logical 52 KiB scratchpad organization, dual weight/scale banks, command sequencing, tail handling, output backpressure, reset/flush behavior, and error propagation.

The bank design allows a host to prepare the inactive bank while compute owns the active bank. Writes to an active compute bank are rejected.

## Numerical contract

Weights use OpenTernary `2bit-v1` semantics:

- `00 = -1`
- `01 = 0`
- `10 = +1`
- `11 = reserved`

See `docs/NUMERICS.md` for exact packing, accumulator, scale, and rounding behavior.

## Host tiling

One command supports K up to 4096. Larger layers are split into multiple commands by the host compiler and accumulated without truncating intermediate row outputs.

## What TPC-X1 is not yet

TPC-X1 is not a complete Transformer accelerator or finished TPU product. Attention, Softmax, RMSNorm, RoPE, KV cache, model loading, tokenizer/sampling, board DMA, and a full runtime are not all integrated yet.

See `docs/INTEGRATION.md` and `docs/ROADMAP.md`.
