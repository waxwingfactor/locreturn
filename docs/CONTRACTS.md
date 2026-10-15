# Supported workflow and contracts

Version 1 supports one source locale and one target locale per job. The maintainer controls baseline, current catalogs, decisions and execution. The returning file is treated as untrusted data. There is no extraction, translation engine, runtime adapter, server, file discovery, subprocess invocation or network access.

## Inputs

All files are regular UTF-8 JSON, without BOM or comments. Duplicate keys anywhere, nonfinite numeric literals and escaped unpaired Unicode surrogates are rejected. Catalog/context objects contain nonempty string keys and string values only. Keys are opaque; no dot splitting, Unicode normalization or whitespace normalization occurs. Empty values are legal. Locale labels follow a bounded language-tag syntax but are not validated against a registry. Text language is not inferred. Aliases other than hyphen/underscore/case normalization are not resolved.

Resource limits: each file <=32 MiB, each catalog <=10,000 entries, combined distinct source/target keys <=10,000, each key <=1,024 Unicode code points, each text/context <=65,536 code points. Source and target labels differ ignoring case and `_`/`-`. Context keys must exist in the corresponding source catalog. Generated files also have the 32 MiB cap. Parsing/serialization is bounded by file size, not constant-memory or hardened against a hostile operating system.

`pack` creates `locreturn.baseline.v1` with source/target snapshots, source/target locale labels, context, and `job_id`; the ID is SHA-256 of compact, sorted, unescaped UTF-8 JSON of the other fields. The baseline belongs in trusted maintainer storage. Retain it for every outstanding return. Identical semantic input yields the same job identity. Jobs do not contain absolute paths or timestamps.

`task.json` is `locreturn.return.v1`, with the job ID and locale labels and an `entries` object. Each source key has `source`, `context`, `previous_target`, and `translation`. Only `translation` is editable. Null is a skip; strings including empty strings are proposals. A return can omit entries but cannot add/rename them, change metadata, add fields or impersonate another locale/job. Missing entries are `not-returned`. This explicit partial-return contract is useful for incremental batches; it does not establish translation completeness.

## Source-qualified merge

For each key, let B be baseline target, C current target and R returned proposal. Missing targets use an internal null sentinel distinct from the string `""`.

1. Keys outside baseline source are `new-source` or `orphan-target`, retained as currently stored.
2. An absent return entry, null proposal, or R=B is `not-returned`, `skipped`, or `unchanged-return`; keep C.
3. For a changed proposal, removed current source is `source-removed`. Changed source **or context** is `source-changed`. Both require review even if R=C.
4. Otherwise R=C is `already-current`; C=B is `ready`; all other cases are `target-conflict`.

Current target deletion and concurrent addition therefore conflict with divergent incoming changes. There is no delete action or pruning, and no source-key rename inference. New source work needs a new job. Returning unchanged target text cannot explicitly reassert it over a local correction; that case intentionally preserves current text. A maintainer who wishes to change it can edit the current catalog in the normal review workflow.

Every plan row includes baseline/current source, context, target, proposal, status and a source-changed boolean. Preserved entries can still have source drift. The plan is `locreturn.plan.v1`, contains a semantic hash of **every** input, all rows, counts and a content ID. Canonicalization uses Python's JSON encoder with `sort_keys=True`, `ensure_ascii=False`, separators `(',', ':')`, no NaN; it is not a claim of RFC 8785 compatibility.

## Decisions and application

`locreturn.decisions.v1` binds exactly the conflict key set to the plan ID. Each entry has `action`, `text` and `reason`. Keep requires null text; incoming requires null text and is allowed only for target conflict. Custom requires a string and is allowed for target conflict/source-changed. Source-removed allows only keep. Reasons are nonempty after stripping, <=4,096 code points. The generated `unresolved` action is deliberately invalid for apply. Unknown/missing decisions or fields fail.

Decisions are reviewed inputs: editing decisions after planning is expected and their final hash/content is captured in the receipt. The plan itself and **all** original/current/returned/context inputs are recomputed and compared by type-sensitive canonical JSON at apply time. A stale plan must be regenerated; transplanting decisions to another plan is refused. No final target is emitted while any conflict lacks a valid decision.

`apply` emits the complete current target with accepted edits as `target.json`, plus `locreturn.receipt.v1`. The receipt includes job/plan IDs, input hashes, decisions hash and content, resulting semantic catalog hash, changed values/reasons and its own ID. These are content-integrity records, not signatures, authorship certificates or approval by a human reviewer. Keep the plan and input snapshots if later reproduction matters.

## Filesystem and trust boundaries

Input symlinks to regular files are readable. The output leaf is exclusively created; existing paths, including symlink leaves, fail. Parents must exist. All data is validated and all output bytes pre-serialized before creating a directory. The CLI never overwrites input catalogs. Ordinary write failures clean only files created by the invocation and attempt removal of its directory. Successful files are flushed and fsynced individually.

Directory publication is not a power-loss atomic transaction. Output may be visible while populated, or remain partial after abrupt termination/cleanup failure. Use it only after exit 0 and verify both target and receipt; retry with a new directory. There is no in-place apply operation. Hostile concurrent writers, network filesystem guarantees, directory symlink substitution, disk failure recovery and authenticated provenance of incoming translations are outside scope. Do not let multiple processes share an output path or mutate inputs while a command runs. Input content is read once per command; apply emits a separate reviewed result rather than promising to lock a running application's catalogs.

Review output JSON-escapes text in `review.txt` so control codes and multiline values do not spoof terminal rows. Machine-readable files may contain arbitrary legitimate translated text; render it as untrusted text in downstream applications.

## Compatibility and quality

Python >=3.10; CI covers 3.10/3.12/3.14 on three OS families. V1 schemas reject unknown fields and schema versions. CLI commands/schema changes follow semantic versioning; internal Python functions are private. No dependency is imported at runtime outside the standard library. Building an sdist requires setuptools>=77 and wheel; wheel installation can be fully offline.

Run your framework's native format, placeholder, plural, markup and linguistic reviews before committing output. locreturn intentionally leaves strings opaque. Exact source/context equality is a conservative identity condition, not a semantic equivalence engine.
