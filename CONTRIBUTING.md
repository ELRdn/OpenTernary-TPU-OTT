# Contributing to OpenTernary TPU (OTT)

Thanks for helping with OTT. The project is still in an early hardware-research phase, so correctness and evidence matter more than headline benchmark numbers.

## Before changing RTL

Read:

- `AGENTS.md`
- `docs/NUMERICS.md`
- `docs/LIMITATIONS.md`
- `reports/results.json`

Preserve the OpenTernary `2bit-v1` mapping and tail rules unless a change is explicitly versioned and documented.

## Validation expectations

For arithmetic or RTL changes:

1. add/update a golden-model test;
2. run the model tests;
3. rebuild the RTL simulation model;
4. run RTL tests after the rebuild (do not reuse stale binaries);
5. run relevant SAT/formal checks;
6. update synthesis evidence if the datapath/resource structure changed;
7. record any skipped or unavailable stage honestly.

Model-only tests must not be described as RTL verification.

## Performance claims

Do not claim a competitive tokens/s, Fmax, or power result from analytical peak throughput or technology mapping alone. Competitive claims require matched model quality, checkpoint, context, I/O boundary, and power-measurement conditions.

## Generated files

Do not commit generated CXXRTL, shared libraries, giant synthesis logs, mapped netlists, Vivado project directories, or bitstreams to normal source commits. Use reproducible scripts plus CI/release artifacts instead.

## Licensing

A project-wide license has not yet been selected. External contributions should not be merged until contribution/licensing terms are made explicit.
