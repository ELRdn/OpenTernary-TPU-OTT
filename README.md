# OpenTernary TPU (OTT)

**OpenTernary TPU (OTT)** is an experimental open hardware project for ternary AI acceleration, designed to pair with [OpenTernary](https://github.com/ELRdn/OpenTernary).

The goal is to co-design the **quantization format, compiler/runtime contract, and accelerator architecture** for efficient ternary inference instead of treating hardware as an afterthought.

> Current architecture: **TPC-X1 — Ternary Processing Core X1**
>
> Status: RTL implemented and tested in simulation; UltraScale+ technology mapping completed; full FPGA board integration and competitive end-to-end LLM performance are **not yet demonstrated**.

## Why OTT?

Ternary weights are restricted to `{-1, 0, +1}`. The main multiply path can therefore be implemented as:

```text
+1 -> +activation
 0 -> 0 / skip
-1 -> -activation
```

TPC-X1 uses this property to avoid conventional multipliers in the ternary MAC hot path while remaining compatible with OpenTernary's canonical packed representation.

## OpenTernary compatibility

The current contract follows OpenTernary `2bit-v1`:

| Code | Weight |
|---|---:|
| `00` | -1 |
| `01` | 0 |
| `10` | +1 |
| `11` | reserved / invalid |

Four ternary values are packed per byte. TPC-X1 also implements G128-oriented group scaling as a separate datapath.

## TPC-X1 at a glance

Default research configuration:

- **R16 × L16 × B4** compute organization
- up to **1,024 ternary products per input cycle** across the tile
- signed INT8 activations
- INT32 group accumulation and INT64 post-scale accumulation
- G128 group scaling
- logical scratchpad: **52 KiB**
- ping-pong weight/scale banks
- command sequencing, tail handling, backpressure, reset/error propagation
- maximum K per command: 4096, with host-side tiling for larger layers

### Verified so far

From the preserved TPC-X1 validation snapshot in [`reports/results.json`](reports/results.json):

- 24 tests passed, 0 failed, 0 skipped
- actual SystemVerilog executed through Yosys/CXXRTL
- 1,000 randomized RTL commands
- 64,000 output values checked
- 3,194,727 active ternary products checked
- 1,500 randomized GEMMs against an independent C++ reference
- 10,000 cycle-spec transactions
- local SAT checks for ternary product, radix-3/T5 decode, and rounding-width equivalence
- no `$mul`, `$macc`, `$div`, or `$mod` in the flattened ternary MAC hot path

### Technology-mapping snapshot

Yosys UltraScale+ mapping after the current width optimization:

| Primitive / node class | Count |
|---|---:|
| LUT1..LUT6 node sum | 56,561 |
| FDRE | 37,274 |
| DSP48E2 | 64 |
| RAMB18E2 | 45 |

The 64 DSPs belong to group scaling, **not** the ternary MAC hot path.

These are technology-mapping counts, **not** placed-and-routed Vivado utilization. No measured Fmax or power claim is made yet.

## Performance target vs. demonstrated performance

The architecture can issue 1,024 ternary products per input cycle. At a hypothetical 250 MHz this corresponds to a peak arithmetic rate of 256 G ternary-products/s, or 0.512 TOPS-equivalent when counting multiply-accumulate as two operations.

**250 MHz is currently a target/assumption, not a measured board clock.** OTT does not yet claim competitive end-to-end tokens/s. The competitive gate remains open until the same checkpoint/quality/context/I/O/power conditions are measured on real FPGA hardware.

See [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) and [`docs/BENCHMARK_PROTOCOL.md`](docs/BENCHMARK_PROTOCOL.md).

## Repository layout

```text
rtl/          synthesizable SystemVerilog for TPC-X1
model/        golden numeric, packing, cycle, and tile compiler models
sim/          CXXRTL bridge and Python bus driver
formal/       local combinational SAT miters
tests/        numeric, compiler, cycle-model, and RTL tests
scripts/      build, verification, synthesis, analysis, and export tools
constraints/  provisional OOC timing constraints
config/       architecture configuration and targets
docs/         architecture, numerics, integration, limitations, research report
reports/      compact preserved validation/synthesis evidence
reference/    research references and toolchain provenance
examples/     synthetic inputs and bus images
licenses/     third-party notices required by generated/runtime components
```

Generated CXXRTL, shared libraries, multi-megabyte logs, mapped netlists, and FPGA build outputs are intentionally excluded from Git. They should be regenerated locally or published as release/CI artifacts.

## Quick start

Python 3.11+ is required.

```bash
python -m pip install numpy pytest
mkdir -p build
g++ -std=c++17 -O2 -shared -fPIC model/reference.cpp -o build/libtpc_reference.so
python -m pytest tests/test_numeric.py tests/test_cycle.py tests/test_compiler.py
```

To rebuild and validate the RTL, a Yosys/CXXRTL-capable toolchain and C++17 compiler are required. Toolchain provenance is recorded in [`reference/toolchain.json`](reference/toolchain.json).

```bash
# Rebuild RTL simulation model, run verification, SAT checks, and synthesis
python scripts/run_all.py --build-rtl --synth

# Model-only checks (does NOT count as an RTL pass)
python scripts/run_all.py --models-only
```

## Architecture documents

- [Architecture](docs/ARCHITECTURE.md)
- [Detailed Japanese architecture notes](docs/ARCHITECTURE.ja.md)
- [Numerical contract](docs/NUMERICS.md)
- [Integration plan](docs/INTEGRATION.md)
- [Benchmark protocol](docs/BENCHMARK_PROTOCOL.md)
- [Known limitations](docs/LIMITATIONS.md)
- [Roadmap](docs/ROADMAP.md)
- [TPC-X1 research report](docs/TPC-X1-RESEARCH-REPORT.md)

## Roadmap

The immediate path is:

1. exact-part Vivado implementation and timing closure
2. board DMA / descriptor integration
3. real OpenTernary model-layer execution on FPGA
4. measured throughput, bandwidth, power, and numerical quality
5. architecture DSE: direct sign-select vs LUT vs sparse / encoded paths
6. Attention/SFU/KV-cache integration
7. matched full-LLM comparison against published ternary accelerators
8. ASIC-oriented exploration after FPGA evidence is solid

## Relationship to OpenTernary

OpenTernary defines and researches the software-side ternary representation and quantization pipeline. OTT is the hardware-side companion project.

```text
OpenTernary
  quantization / packing / calibration
             |
             v
OpenTernary TPU (OTT)
  compiler contract / accelerator / FPGA / future ASIC
             |
             v
TPC-X1 -> future TPC generations
```

The projects are intentionally separate so hardware experimentation can evolve without destabilizing the software repository.

## License status

A project-wide open-source license has **not yet been selected**. See [`LICENSE_STATUS.md`](LICENSE_STATUS.md). Third-party notices are kept under [`licenses/`](licenses/).

Until a license is explicitly added, do not assume permission to redistribute or reuse the project code beyond what copyright law otherwise permits.

## Research integrity

OTT is intentionally conservative about performance claims. Analytical TOPS, technology mapping, CXXRTL correctness, placed-and-routed timing, board measurements, and end-to-end LLM tokens/s are different evidence levels and are reported separately.
