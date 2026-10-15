# Opportunity, alternatives and positioning

Evidence reviewed **2026-10-15**. This is a bounded desk-research assessment by AI agents, not customer discovery interviews, adoption evidence, an exhaustive market census, or proof of universal uniqueness. Sources can change after this date.

## Documented problem and inferred audience

[Godot's own translator guide](https://github.com/godotengine/godot-contributing-docs/blob/main/other/translations.rst) warns that delayed offline translation uploads can overwrite other contributors' intervening work. It recommends online Weblate editing. Godot uses PO, which locreturn does not support; the guide establishes a concurrency problem class, not a prospective customer relationship.

[LiftTrace's contribution guide](https://github.com/TraceApps/lifttrace/blob/main/CONTRIBUTING.md) explains that English text can change under the same JSON key and asks translators to diff against the original version to identify stale translations. It also provides Weblate as a preferred workflow. The current guide includes nested JSON, which is outside locreturn's supported flat scope; it documents source-drift pain without establishing exact format fit.

[OneTimeSecret issue #2015](https://github.com/onetimesecret/onetimesecret/issues/2015) documents recurring locale JSON conflicts across contributor updates and branch merges, and proposes an existing semantic merge driver. Basic JSON merge is already addressed; this issue is evidence of a problem and an effective alternative, not evidence that locreturn is required.

**Inference:** a small group maintaining flat JSON catalogs, exchanging files outside a TMS, and continuing copy/target edits during a handoff may benefit from local per-key source-qualified reconciliation. That exact demand remains unvalidated. A generic translation checker, metadata inventory, CSV exporter or JSON merge wrapper was rejected as too crowded and insufficiently differentiated.

## Three competition checks

The lead and two independent AI agents searched primary product documentation, open-source repositories and concrete import/merge implementations. Native platforms were checked first, standalone handoff tools second, and semantic merge/versioned synchronization third. The resulting scope combines established ideas into a deliberately small service-free workflow.

| Alternative | Documented strength | Why choose it / locreturn boundary |
|---|---|---|
| [Weblate offline files](https://docs.weblate.org/en/latest/user/files.html) | Offline exports/imports into changed translations; review, language metadata and conflict policies based on untranslated/translated/approved state | Prefer it for ongoing translator collaboration. This page does not document an exported source+target baseline comparison per returned key. |
| [Crowdin offline translation](https://support.crowdin.com/offline-translation/) and [version management](https://support.crowdin.com/version-management/) | CAT-friendly XLIFF and original formats; project branches and conflict handling | Prefer it for a managed project and translation teams. locreturn avoids service setup and requires its own small JSON return format. |
| [Lokalise offline translation](https://docs.lokalise.com/en/articles/2561895-offline-translation) and [branching](https://docs.lokalise.com/en/articles/3391861-project-branching) | Source verification/retranslation on offline return; per-key branch conflicts | Source validation is established. Prefer it when centralized reviews and branch workflows fit. locreturn hard-blocks changed-source incoming text and compares original/current targets locally. |
| [Phrase branching](https://support.phrase.com/hc/en-us/articles/5856411356316-Branching-Strings) | Base/branch conflict detection and merge strategies | A strong platform alternative, not an absent capability. |
| [Tolgee CLI](https://docs.tolgee.io/tolgee-cli/push-pull-strings) and [branching](https://docs.tolgee.io/platform/branching/overview) | Framework integrations, push/pull conflict modes and project branching | Prefer for hosted/self-hosted localization operations. locreturn has no server or runtime integration. |
| [BabelEdit import/export](https://www.codeandweb.com/babeledit/documentation/import-export) | Multi-language editing and translator CSV round trips | Prefer its editor and broader format support. Import documentation specifies IDs/language columns; it does not describe source+target export-baseline reconciliation. |
| [Trox handoff](https://github.com/thurn/trox) | Protected workbook, identity/placeholder checks; rejects changed source catalogs and canonical CSV edits | Excellent when adopting its Rust/TypeScript localization system. locreturn selectively reconciles independent returned edits against existing flat JSON without adopting that runtime. |
| [LocalizationManager import](https://github.com/nickprotop/LocalizationManager/blob/main/docs/COMMANDS.md) | Format support, backups and CSV imports, with fill-missing or overwrite policies | Good broad resource editor; documented import policy differs from source-qualified baseline comparison. |
| [i18nsmith CSV importer at 44e757f](https://github.com/IMAGINARY9/i18nsmith/blob/44e757feea49c9ffc1f08f04d62f1947f79ad6da/packages/cli/src/commands/translate/csv-handler.ts) | Useful offline CSV handoff and placeholder validation | Inspection found validation against CSV source text and overwrite/fill behavior, without a retained target baseline or current-source comparison in that importer. This does not claim every other command behaves identically. |
| [i1n comparator at 94be41d](https://github.com/Pakvothe/i1n-cli/blob/94be41d5866d6b5d92fa63ad6f432605e71f1b2c/src/shared/push-state.ts) | Real three-way hosted synchronization per namespace/key/language | Inspection found no source-locale argument or cross-language source gate in this comparator. Inference: that comparator alone does not provide locreturn's source-qualified return rule. No claim is made about all server semantics. |
| [git-json-merge](https://github.com/jonatanpedersen/git-json-merge) / Git | Established common-ancestor structured/text merge | Prefer for ordinary branch merges. A target-file merge alone does not compare a separately changed source catalog/context. locreturn implements its own per-entry rules rather than wrapping the command. |
| [Translate Toolkit pomerge](https://docs.translatehouse.org/projects/translate-toolkit/en/latest/commands/pomerge.html) | Applying corrected PO/XLIFF/TMX snippets with configurable fuzzy/blank behavior | Prefer for supported bilingual formats. locreturn handles explicitly paired flat-JSON source/target snapshots. |

Absence of a feature from one documentation page is not proof that a product cannot do it. None of these checks establish a monopoly on this workflow. If a native platform already fits, introducing another return format adds friction and locreturn may be the wrong choice.

## Applying Crossing the Chasm selectively

[Geoffrey Moore's own book page](https://geoffreyamoore.com/book/crossing-the-chasm/) emphasizes target segment, compelling reason, whole product and positioning versus incumbent alternatives. [Moore's Chasm Group article](https://chasmgroup.com/crossing-the-chasm-whats-new-whats-not/) provides the original author's continuing perspective. We apply those ideas to scope and usability, not an invented financial/distribution strategy.

**Beachhead:** developer-maintainers of small applications with flat JSON catalogs who exchange one locale's human translation file outside a TMS and keep editing during the return interval. Translators need only a JSON editor; maintainers need Python and their existing application checks.

**Compelling reason:** accept independent safe work while making competing target edits and changed source/context visible before any final catalog is emitted. Reissuing an entire handoff or manually correlating two target histories and two source versions is avoidable within this narrow scope.

**Market alternative:** manually compare the returned file with current JSON and original source snapshots in an editor/Git. **Product alternative:** adopt Weblate or another TMS for shared state, reviews and offline uploads. Both alternatives are valid and often preferable.

**Original two-sentence positioning:** For maintainers of small flat-JSON application catalogs who are dissatisfied with manually correlating delayed translator returns and intervening copy corrections, locreturn is a local translation-return reconciler that qualifies every incoming edit against original and current source, context and target text. Unlike adopting a translation management platform for this single handoff, locreturn supplies the complete file-only workflow: a trusted baseline, editable task, per-key review plan, reasoned conflict decisions, stale-plan refusal, a new target and a reproducible content receipt.

**Whole supported product:** installable wheel/sdist, offline CLI, explicit contracts and limits, error codes, task/decision templates, human review text, complete output, audit receipt, examples, acceptance tests, independently reviewed code and actual release-artifact verification. No reference customers, measured savings or production deployments are claimed.

## Constructed usage scenarios

These are invented examples, not observations or endorsements.

1. An open-source desktop utility sends a French task on Monday. A maintainer corrects one French button while the translator changes another. locreturn accepts the independent change and preserves the local correction; divergent edits to the same button need a decision.
2. English “Save” changes to “Save backup” during translation. The incoming French text is source-changed even if its target matches current French. A reviewer retains current text or writes a custom translation against “Save backup,” with a reason.
3. A key's spelling stays identical but its context changes from a financial bank to a river bank. Supplying updated context blocks stale incoming work. Without updated text or context, no deterministic equality tool can infer the meaning change.
