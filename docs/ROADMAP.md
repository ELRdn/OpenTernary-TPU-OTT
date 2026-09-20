# OpenTernary TPU (OTT) Roadmap

## Phase 1 — TPC-X1 evidence closure

- exact FPGA part selection
- Vivado synthesis / place / route
- timing closure with measured achievable Fmax
- post-route resource and power estimates
- CDC/bus-wrapper design where required

## Phase 2 — Board execution

- DMA / descriptor path
- host driver or runtime bridge
- load packed OpenTernary weights directly
- execute a real model linear layer
- compare RTL output against OpenTernary software output
- measure sustained bandwidth and board power

## Phase 3 — Architecture DSE

Compare under the same FPGA target and numerical contract:

- direct sign-select
- LUT-based ternary groups
- sparse zero-skip scheduling
- denser ternary encodings such as radix-3/T5 transport
- group-size and scale-format alternatives

Selection criteria include area, Fmax, energy, bandwidth, quality impact, and end-to-end latency.

## Phase 4 — Transformer coverage

- RMSNorm / normalization support
- RoPE
- Attention support
- Softmax/SFU strategy
- KV-cache movement and layout
- embedding / LM-head strategy
- prefill and decode scheduling

## Phase 5 — Competitive benchmark gate

Use matched conditions against published ternary accelerators:

- same or clearly comparable checkpoint
- reported model quality
- fixed prompt/context regime
- explicit I/O measurement boundary
- tokens/s
- prefill latency / throughput
- board/system power
- energy per token
- FPGA resource usage and clock

Only after this phase may OTT make an end-to-end competitive-performance claim.

## Phase 6 — TPC-X2 and beyond

Use measured results to design the next architecture rather than assuming one technique wins universally. Candidate improvements include more aggressive weight reuse, compression-aware streaming, sparse scheduling, fused scaling/activation paths, and ASIC-oriented memory hierarchy work.
