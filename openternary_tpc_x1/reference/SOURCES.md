# 一次資料一覧

本文の文献番号に対応する。論文や第三者リポジトリのコード一式は同梱していない。

## S01 — TeLLMe: An Energy-Efficient Ternary LLM Accelerator for Prefill and Decode on Edge FPGAs

arXiv:2504.16266v2, 2025-04-24

Paper text and Tables III-V, Figures 9-10 inspected; reported FPGA results, not independently reproduced.

```text
https://arxiv.org/pdf/2504.16266v2
```

## S02 — TerEffic: Highly Efficient Ternary LLM Inference on FPGA

arXiv:2502.16473v2, 2025-05-01

Paper model/card scope, evaluation and Vivado power-report methodology inspected; not a matched Transformer baseline.

```text
https://arxiv.org/pdf/2502.16473v2
```

## S03 — Hardware Generation and Exploration of Lookup Table-Based Accelerators for 1.58-bit LLM Inference

arXiv:2604.25183v1, 2026-04-28

Table IV and INT8/FP16 design-space results inspected. ASIC synthesis, not board LLM throughput.

```text
https://arxiv.org/pdf/2604.25183v1
```

## S04 — KU Leuven MICAS ternary-lut-dse

accessed 2026-09-20

Official generator README; architecture reference, source not copied.

```text
https://github.com/KULeuven-MICAS/ternary-lut-dse
```

## S05 — TERINT-GEMV official repository

accessed 2026-09-20

81-to-64 codebook restriction and fine-tuning, RTL and SoC estimator scope checked.

```text
https://github.com/Notre-Dame-HW-SW-Codesign-Lab/TERINT-GEMV
```

## S06 — Microsoft T-MAC

accessed 2026-09-20

Official CPU/NPU low-bit LUT inference framework; no direct FPGA speed transfer.

```text
https://github.com/microsoft/T-MAC
```

## S07 — Microsoft BitNet

accessed 2026-09-20

Official low-bit model/runtime reference; not executed here.

```text
https://github.com/microsoft/BitNet
```

## S08 — fpgasystems/ternaryLLM

accessed 2026-09-20

Sparse addition-based GEMM reference; model-specific sparsity must be measured.

```text
https://github.com/fpgasystems/ternaryLLM
```

## S09 — Berkeley Gemmini

accessed 2026-09-20

Official scratchpad, DMA, access/execute and loop-tiling design reference.

```text
https://github.com/ucb-bar/gemmini
```

## S10 — FINN documentation

accessed 2026-09-20

FPGA quantized neural-network framework documentation; not used as a backend.

```text
https://finn.readthedocs.io/en/latest/
```

## S11 — AMD KV260 Starter Kit Product Details DS986

DS986 1.3, 2025-06-25

Official resources: system logic cells, BRAM, URAM, DSP, DDR. Not all counts share paper units.

```text
https://docs.amd.com/r/en-US/ds986-kv260-starter-kit/Product-Details
```

## S12 — OpenTernary canonical packing contract

commit 31564aeff6b03a46942ef048715058f4b5cba320

Read through user-authorized GitHub connector; 2bit mapping, MSB-first codes, 00 tail. Blob fdc55ffa06009bd15572ece07d640e765fc56394. Independent implementation, no copied function.

```text
https://github.com/ELRdn/OpenTernary/blob/31564aeff6b03a46942ef048715058f4b5cba320/src/openternary/quant/packing.py
```

## S13 — Official Yosys toolchain workflow

head d0e71cfb7bcafe2b437f3edc1789b69e99ecd55a, 2026-09-13

Official wheel downloaded via read-only GitHub artifact tool and actually executed; see toolchain.json.

```text
https://github.com/YosysHQ/yosys/actions/runs/34751481437
```

## S14 — AMD K26 SOM datasheet DS987

accessed 2026-09-20

Official datasheet entry point; exact-part integration must use the board-specific device data.

```text
https://docs.amd.com/r/en-US/ds987-k26-som
```

