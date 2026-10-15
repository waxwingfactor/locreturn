# Verification and review record

## Development review, 2026-10-15

Two separate AI agents independently reviewed the opportunity and challenged existing alternatives. They are AI-agent assessments, not human reviews or independent GitHub accounts.

The testing agent wrote 32 adversarial acceptance tests and ran them independently on Python 3.12.13. The lead's suite adds 17 tests, including an exhaustive 64-case target-state table and CLI round trips. All 49 tests passed locally on macOS/Python 3.12 before the implementation PR.

A separate code/security reviewer read all five source files, ran 192 finite-state cases and 17 CLI probes, and reported one P3 issue: Python equality accepted boolean/number substitutions in a modified plan. The lead changed comparison to canonical JSON bytes; both independent agents verified the regression now fails safely. No blocking findings remained within the supported CLI/single-writer scope. Core file SHA-256 reviewed after the fix: `8e2202007a9c722b23d1975a1b4d48ab699d55f8bbb6acc5791f38557241b352`.

The tests cover concurrent deletion/addition, empty vs absent targets, source/context drift, unknown and duplicate keys, invalid Unicode, stale input/plan/decisions, output overwrite/symlink refusal, midwrite cleanup, FIFO refusal, resource limits, terminal escaping and relocation. Runtime translation quality is explicitly outside scope.

## Release process

The protected main branch requires `quality-gate`, aggregating four OS/Python test jobs (Linux 3.10/3.14, macOS 3.12, Windows 3.12) and Linux 3.12 distribution installation checks. This targets minimum/recent interpreter compatibility and cross-platform filesystem behavior without multiplying every combination. The single maintainer records separate AI-agent review evidence in PR comments and merges only after required checks pass; no human self-approval is represented as independent review.

CI builds wheel/sdist, installs both outside the checkout in separate fresh environments, runs the full suite and constructed example, and uploads artifacts with a manifest recording source revision and Actions run. Release assets are taken from the passing main-branch CI build, with a SHA-256 checksum file. These provenance records identify the build; they are not third-party signatures.

## Actual public release verification, 2026-10-15

[Release v1.0.0](https://github.com/waxwingfactor/locreturn/releases/tag/v1.0.0) was published at 19:29:20 UTC. A separate AI testing agent independently downloaded its **actual public assets without authentication**, then verified them from 19:29:49 to 19:30:01 UTC on macOS 26.5 arm64 / Python 3.12.13. [Redacted raw evidence](PUBLIC_VERIFICATION.json) records requests, exact commands, results, environment, code comparisons and hashes. Its SHA-256 is `d940bfaa33c79ca696fb973c840d4c065f693f751a98435989614ab9b38ed955`.

| Published artifact | SHA-256 |
|---|---|
| `locreturn-1.0.0-py3-none-any.whl` | `e5633fadd34dcd7b8a325b291da9eab9c5e38045ec17208c7738b99590c85472` |
| `locreturn-1.0.0.tar.gz` | `39353ce503da41a0af90c39a6b409a8afc1538f34c7598f2150eab7eb080e934` |

The public tag resolves to source commit `b4606c3d7e940a624c5c436d4bcf8b1ead050083`. [Main CI run 38794149241](https://github.com/waxwingfactor/locreturn/actions/runs/38794149241) and all six jobs passed for that revision. Downloaded checksums and provenance match artifact bytes; the lead also checked GitHub's release-asset digest fields. The independent verifier checked the wheel RECORD hashes and all five Python code files against the public source tag. The sdist's source, tests, examples and documentation match the tag.

Separate fresh environments installed the downloaded wheel and built/installed the downloaded sdist, using `--no-index` and predownloaded build-tool wheels for the latter. No editable installation, checkout import, `PYTHONPATH` or user-site leakage was used. Each installed artifact passed all **49 published acceptance tests**, the published demo, the console entrypoint, and an independently constructed workflow. Import origins were inside each environment's site-packages.

For both installs, a Python audit hook blocked all socket events and a connection probe confirmed the block. The full tests, example and independent workflow then ran under that block. The independent workflow moved its catalogs/task/plan after review, preserved local target corrections and orphan targets, required source/context/target conflict decisions, checked receipt/output hashes and untouched input targets, and refused unresolved conflicts, stale-source incoming decisions and stale plans without final output.

The lead separately downloaded the actual public wheel anonymously (HTTP 200), checked the same SHA-256, installed it in another fresh environment with `--no-index --no-deps`, verified isolated import/version and ran the installed console help. An initial lead harness used a virtual-environment API that failed to bootstrap this bundled interpreter; changing that harness to the documented `python -m venv` command succeeded. No published artifact was changed.

The [independent verifier](verify_public_release.py) is preserved for reproduction. It fetches public assets and the public tag, has no local-dist fallback, and requires a new output directory:

```sh
python3.12 docs/verify_public_release.py \
  --release-url https://github.com/waxwingfactor/locreturn/releases/tag/v1.0.0 \
  --source-commit b4606c3d7e940a624c5c436d4bcf8b1ead050083 \
  --ci-run-id 38794149241 --out verification-run
```

This record describes synthetic acceptance scenarios, not customer adoption, translation-quality validation or production deployment. Public wheel/sdist verification was on one macOS/Python environment; cross-platform evidence is the separate CI matrix. Provenance and checksums are content records, not third-party signatures. The release tag/assets stay at the verified source revision; this post-release evidence is added through a subsequent documentation PR.
