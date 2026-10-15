# Verification and review record

## Development review, 2026-10-15

Two separate AI agents independently reviewed the opportunity and challenged existing alternatives. They are AI-agent assessments, not human reviews or independent GitHub accounts.

The testing agent wrote 32 adversarial acceptance tests and ran them independently on Python 3.12.13. The lead's suite adds 17 tests, including an exhaustive 64-case target-state table and CLI round trips. All 49 tests passed locally on macOS/Python 3.12 before the implementation PR.

A separate code/security reviewer read all five source files, ran 192 finite-state cases and 17 CLI probes, and reported one P3 issue: Python equality accepted boolean/number substitutions in a modified plan. The lead changed comparison to canonical JSON bytes; both independent agents verified the regression now fails safely. No blocking findings remained within the supported CLI/single-writer scope. Core file SHA-256 reviewed after the fix: `8e2202007a9c722b23d1975a1b4d48ab699d55f8bbb6acc5791f38557241b352`.

The tests cover concurrent deletion/addition, empty vs absent targets, source/context drift, unknown and duplicate keys, invalid Unicode, stale input/plan/decisions, output overwrite/symlink refusal, midwrite cleanup, FIFO refusal, resource limits, terminal escaping and relocation. Runtime translation quality is explicitly outside scope.

## Release process

The protected main branch requires `quality-gate`, aggregating four OS/Python test jobs (Linux 3.10/3.14, macOS 3.12, Windows 3.12) and Linux 3.12 distribution installation checks. This targets minimum/recent interpreter compatibility and cross-platform filesystem behavior without multiplying every combination. The single maintainer records separate AI-agent review evidence in PR comments and merges only after required checks pass; no human self-approval is represented as independent review.

CI builds wheel/sdist, installs both outside the checkout in separate fresh environments, runs the full suite and constructed example, and uploads artifacts with a manifest recording source revision and Actions run. Release assets are taken from the passing main-branch CI build, with a SHA-256 checksum file. These provenance records identify the build; they are not third-party signatures.

Actual post-publication download and installation evidence will be recorded after release in this document and the release notes. A local build or CI artifact alone is not described as a verified public release.
