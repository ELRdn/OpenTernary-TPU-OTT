# TPC-X1 development contract

Read README.md, docs/NUMERICS.md, docs/LIMITATIONS.md and reports/results.json before editing.
This repository is a tested tile accelerator, not a finished full-LLM FPGA product.
Do not call the final competitive-performance gate closed without matched quality,
checkpoint, context, I/O and power measurements.

Preserve canonical OpenTernary 2bit-v1 mapping, byte order, tail rules and per-group
scale boundaries. Do not change numerical precision or discard required rotations
without an explicit experiment record. K-tile results share one row output unit
and remain INT64 until all partials are accumulated.

Actual RTL tests use Yosys-generated CXXRTL. Python cycle-model tests are a separate
layer of evidence. Rebuild after every RTL/bridge change; stale-binary hashes must
not be disabled. Report skipped tests and unmet timing targets as such.

The current highest-priority missing pieces are exact-part Vivado implementation,
board DMA/descriptor integration, real-model numerical validation, and the
Attention/SFU/KV/full-model runtime. Do not hide their cost in performance reports.
Keep original source, logs, tool versions, source fingerprints and experiments.
Do not push to the user's OpenTernary repository or launch paid hardware/services
without an explicit request. Original project code is licensed under Apache-2.0 (see LICENSE, NOTICE, TRADEMARKS.md).
