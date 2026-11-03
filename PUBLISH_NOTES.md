# OTT public-repository cleanup notes

This tree is the cleaned public-source layout prepared from the TPC-X1 validation package.

## Main changes

- promoted the TPC-X1 source layout to repository root for a clean standalone repository
- added a project-level `README.md` for **OpenTernary TPU (OTT)**
- added `CONTRIBUTING.md`
- added `.gitignore` for generated RTL/synthesis artifacts
- added GitHub Actions model/compiler CI
- added English `docs/ARCHITECTURE.md`
- added `docs/ROADMAP.md`
- moved the long-form TPC-X1 research report to `docs/TPC-X1-RESEARCH-REPORT.md`
- kept compact JSON/CSV synthesis and validation evidence
- removed generated CXXRTL C++, shared libraries, giant netlists and multi-megabyte logs from the source package
- retained third-party notices and toolchain provenance

## License

The project is licensed under the Apache License 2.0 (`LICENSE`, `NOTICE`, `TRADEMARKS.md`), matching the parent OpenTernary repository's decision of 2026-11-03. The earlier `LICENSE_STATUS.md` (license TBD) was removed.

## Local validation of this cleaned tree

Before removing generated files for publication, the cleaned layout was tested by rebuilding the C++ reference library and running:

```text
python -m pytest -q tests/test_numeric.py tests/test_cycle.py tests/test_compiler.py
```

Result:

```text
17 passed, 1 skipped
```

The single skipped test requires the generated actual-RTL CXXRTL shared library, which is intentionally not committed. The preserved full validation snapshot remains in `reports/results.json` and records the earlier full package verification.
