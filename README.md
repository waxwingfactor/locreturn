# locreturn

Reconcile an offline translator's JSON return after your source text and local translations have moved on.

`locreturn` snapshots the original source, optional translator context, and target catalog. When a translation returns, it compares that baseline with current files, accepts independent safe edits, and requires explicit decisions for source drift or competing target changes. It writes a new target and a content-bound receipt; it never edits your input catalogs.

This tool is for maintainers who already exchange JSON catalogs outside a translation management system. Weblate, Crowdin, Lokalise, Phrase, Tolgee and BabelEdit are strong alternatives when their broader workflows fit.

## Install

Python 3.10 or newer. Download the wheel from the [public release](https://github.com/waxwingfactor/locreturn/releases/latest), then install it in an isolated environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install ./locreturn-1.0.0-py3-none-any.whl
.venv/bin/locreturn --help
```

On Windows, use `.venv\Scripts\python.exe` and `.venv\Scripts\locreturn.exe`. The installed tool has no dependencies, server, credentials, telemetry, or network calls. The release also includes an sdist with docs, examples and tests; building it needs setuptools and wheel.

## Use

Catalogs are **flat JSON objects with string values**. Dots in keys are literal; nested objects, arrays, numbers and JSON comments are unsupported. Use `{}` as the target file for a new locale.

```sh
locreturn pack --source en.json --target fr.json \
  --source-locale en --target-locale fr --out job
```

Keep `job/baseline.json` unchanged with the maintainer. Give the translator `job/task.json`. They edit only each entry's `translation`:

```json
{
  "source": "Save",
  "context": null,
  "previous_target": "Sauver",
  "translation": "Enregistrer"
}
```

`null` means no proposal; `""` means an intentional empty translation. A translator may omit entries for a partial return. Keys and identity fields cannot change. All ordinary JSON editors work; this is not a CAT or spreadsheet interchange format.

After receiving the task, plan against **current** catalogs:

```sh
locreturn plan --baseline job/baseline.json --returned job/task.json \
  --source en.json --target fr.json --out review
```

Review `review/review.txt` and `review/plan.json`. Exit **3** means the plan was written and contains conflicts. Fill every entry of `review/decisions.json`, using a nonempty reason. For example:

```json
{"action": "keep", "text": null, "reason": "Preserve the local reviewer correction"}
```

For a target conflict, choose `keep`, `incoming`, or `custom`. For changed source/context, choose `keep` or `custom` with text reviewed against the current source. Removed source allows only `keep`. The tool never imports stale-source text through an `incoming` decision.

```sh
locreturn apply --baseline job/baseline.json --returned job/task.json \
  --source en.json --target fr.json --plan review/plan.json \
  --decisions review/decisions.json --out merged
```

When there are no conflicts, omit `--decisions`. Apply recomputes the entire plan and refuses changed inputs or modified plans. Review `merged/target.json` and `merged/receipt.json`, run your application's translation/placeholder checks, then commit the reviewed target through your normal workflow. Every `--out` must be a new directory with an existing parent; there is no overwrite mode.

For semantic context such as “bank: financial account,” add `--context context.json` to **all three commands**. This optional flat key-to-string map participates in source identity. Omitting previously supplied context makes those entries source-changed.

## Behavior and boundaries

| Situation | Result |
|---|---|
| Source/context match; target unchanged since export | Accept the incoming edit |
| Returned target unchanged, missing, or null | Preserve current target |
| Incoming and current target agree | Keep current target |
| Both targets changed differently, including current deletion | Require a target-conflict decision |
| Source text/context changed or source key removed | Block incoming; require review |
| New source key or orphan target | Report and preserve current target; never invent or prune |

Success certifies reconciliation under these rules, **not** completeness, linguistic quality, runtime syntax, or currency of every existing translation. Existing stale targets may be retained. Placeholder checks, ICU/plural interpretation, semantic equivalence, renames, automatic translation, TMS synchronization, nested JSON, and baseline-free imports are outside scope. If meaning changes without source text or context changing, locreturn cannot detect it.

Up to 10,000 combined distinct keys, 1,024 characters per key, 65,536 per value and 32 MiB per input/generated file. Full inputs and plans are held in memory; large catalogs may exceed the generated-file limit and must be split. Local single-writer filesystems are supported; directories may be visible during writing. Ordinary write failures attempt cleanup. A crash/power loss may leave a partial output directory: use output only after exit 0 and create a new directory on retry. Original inputs remain untouched. Hashes detect accidental changes; they do not authenticate a malicious party who can rewrite your trusted baseline.

Exit codes: **0** completed, **2** invalid/unsupported input or I/O failure, **3** plan written with unresolved conflicts. JSON summaries go to stdout and errors to stderr. Input formatting/order changes do not stale a plan; parsed content changes do.

See [contracts and trust boundaries](docs/CONTRACTS.md), [research and positioning](docs/RESEARCH.md), [release verification](docs/VERIFICATION.md), and the [constructed example](examples/demo.py).

## Develop

```sh
python3 -m pip install -e . build
python3 -m unittest discover -s tests -v
python3 examples/demo.py
python3 -m build
```

CI checks the minimum and newest supported Python generations on Linux (3.10/3.14), filesystem behavior on macOS/Windows (3.12), and wheel/sdist installation outside the checkout (Linux 3.12). The CLI and v1 JSON schemas are supported interfaces; internal Python modules are not a stable library API. MIT licensed.
