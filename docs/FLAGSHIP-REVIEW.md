# Four architecture decisions: a 30-minute evidence review

Documentation edition: 10 November 2026. These are four independent, AI-assisted C#/.NET synthetic/local laboratories prepared for Pouria Jamali. The review connects decisions and evidence; it does not describe an integrated trading platform, production deployment or a record of managing a team.

## Start with the responsibility, then inspect its failure boundary

| Project | Responsibility to examine | Frozen runtime and case study |
| --- | --- | --- |
| Trading Execution Lab | Commit a reservation, original receipt and audit together; make an unknown reply visible | [`v0.5.2-preview.1`](https://github.com/pouriajamali/trading-execution-lab/releases/tag/v0.5.2-preview.1) · [Case study](ARCHITECTURE-CASE-STUDY.md) |
| Fenced Shard Ownership Lab | Reject an old writer at committed sink cutover and keep business identity across generations | [`v0.1.0-preview.2`](https://github.com/pouriajamali/fenced-shard-ownership-lab/releases/tag/v0.1.0-preview.2) · [Case study](https://github.com/pouriajamali/fenced-shard-ownership-lab/blob/main/docs/ARCHITECTURE-CASE-STUDY.md) |
| Contract Evolution Lab | Separate wire compatibility, semantic permission and the database point of no return | [`v0.1.0-preview.1`](https://github.com/pouriajamali/contract-evolution-lab/releases/tag/v0.1.0-preview.1) · [Case study](https://github.com/pouriajamali/contract-evolution-lab/blob/main/docs/ARCHITECTURE-CASE-STUDY.md) |
| Tail-Latency Evidence Bench | Keep rejected and unfinished work visible before interpreting a percentile | [`v0.1.0-preview.1`](https://github.com/pouriajamali/tail-latency-evidence-bench/releases/tag/v0.1.0-preview.1) · [Case study](https://github.com/pouriajamali/tail-latency-evidence-bench/blob/main/docs/ARCHITECTURE-CASE-STUDY.md) |

Each case follows **problem → architectural decision → excluded alternatives → counterexample/failure → versioned evidence → limits**. Each includes short English and Persian introductions. Its `FLAGSHIP-EVIDENCE.json` records the runtime commit/tree, signed tag object, public tag CI, six published asset identities and named source evidence.

Links to `main` are navigation to current documentation. Code/test links inside a case are pinned to its frozen runtime commit. Later README/documentation commits do not replace the source identity of an existing binary or justify a new binary release.

## Before the session

This route can be completed by reading existing source and receipts. Downloading dependencies, setting up PostgreSQL/etcd or running a full integration matrix is **outside** the 30-minute allowance. A fresh reproduction is optional and separate; follow the exact release's prerequisites, provenance instructions and new-output-directory rules. This documentation work did not run new tests, benchmarks, service fixtures or release builds locally.

Prepare four tabs: a case study, its evidence index, its frozen named test and its exact public tag CI. For an actual demo, use a verified already-prepared local package and synthetic state. Do not substitute a slide or browser JavaScript model for evidence that the C# backend ran. Keep generated connection files, run-only credentials and private traces out of shared material.

## 30-minute walkthrough

| Minutes | Presenter action | Reviewer question | Evidence / answer boundary |
| --- | --- | --- | --- |
| 00–03 | State the role and four responsibilities; identify each runtime tag | What would you be willing to claim from these artifacts? | Bounded design/test evidence. No production, adoption, people-management or speed-superiority claim |
| 03–09 | Execution: draw the SQLite commit, then describe an unreadable reply | Can a timeout be treated as rollback? Can an old replay replace current state? | No. Retain exact identity, resolve the original receipt, fetch current state separately. Open `HistoricalRetryDoesNotRollbackLaterCommittedState` and the pre-commit rollback test |
| 09–15 | Fencing: draw pause → new committed sink activation → old request resumes | Does a new lease alone reject the stale actor? What changes across generations? | The sink checks the active fence. Business identity survives a generation. Inspect the paused-in-flight and same-identity recovery cases |
| 15–21 | Evolution: compare ticks with confirmed milli-ticks; draw stages 0/1/2 | Why can a wire-compatible message be unsafe? Where does rollback stop? | Explicit semantics/presence can deny. Stage 1 rollback is demonstrated; stage 2 is blocked. Inspect the immutable-old-writer pre-fill guard, not just final numbers |
| 21–26 | Latency: reconstruct all four accounting partitions before reading ranks | Where are the missing requests? Does an isolated clock-read cost correct total latency? | Misses/rejections/censoring stay visible. Primitive observer measurements are separate and are not subtracted. Default cases do not support the p99.9 display floor |
| 26–30 | Let the reviewer choose one counterexample and one changed assumption | What would fail if we added another sink, site, tenant or workload? | Name the missing invariant, propose one falsifiable follow-up and state what the present evidence cannot establish. Do not claim it was already implemented |

The final four minutes should reveal reasoning, not memorized headings. Ask the presenter to locate the enforcing code, explain an excluded alternative and identify the smallest experiment that could disprove their explanation. A successful walkthrough is an observation of understanding in that session; it is not automatically proof of independent authorship or leadership history.

## Evidence questions that make the discussion useful

1. **Identity:** Which commit built the runtime? Is the green CI for that tag, a source push, or a later docs commit?
2. **Observable behavior:** Which named test, raw receipt or database-history check could falsify the stated invariant?
3. **Ownership:** Which component serializes the decision, and who owns cleanup or uncertainty at each boundary?
4. **Alternatives:** What availability, parallelism, operational burden or expressiveness was traded away? Which alternatives were reasoned about rather than measured?
5. **Scope:** Was it a local unit, extracted native package, Linux service fault, Windows-to-WSL observation or development trace? Do not merge them into an unqualified count.
6. **Team discussion:** What would API, database and operations reviewers need to agree before changing the contract? These are proposed review responsibilities, not a claim that a real team performed them.

The listed checks cover selected invariants. They are not an exhaustive code or security audit, and a passing release does not imply zero remaining defects. Existing scope and upstream notices remain part of every project.

## Short introduction — English

Four AI-assisted C#/.NET case studies examine durable reservations, stale-writer fencing, versioned rollout and overload accounting. Each connects a concrete architectural decision to a counterexample, named tests and a frozen public release. They are synthetic local labs for discussing engineering judgment, with explicit limits around production, performance, adoption and personal leadership claims.

## معرفی کوتاه — فارسی

این چهار مطالعهٔ موردی C#/.NET با کمک هوش مصنوعی، رزرو پایدار، کنترل نویسندهٔ قدیمی، تحول نسخه‌ها و حسابرسی بار اضافی را بررسی می‌کنند. هر تصمیم به یک مثال نقض، آزمون مشخص و ریلیز ثابت وصل است. هدف، گفت‌وگوی قابل‌استناد دربارهٔ قضاوت مهندسی است؛ این آزمایشگاه‌های مصنوعی و محلی، سابقهٔ production، استفادهٔ واقعی دیگران یا مدیریت تیم را به‌تنهایی اثبات نمی‌کنند.

## راهنمای ارائهٔ فارسی

سه دقیقهٔ اول هدف و نسخه‌ها را روشن کن. سپس به‌ترتیب شش دقیقه برای Execution، شش دقیقه برای Fencing، شش دقیقه برای Contract Evolution و پنج دقیقه برای Latency بگذار. در چهار دقیقهٔ آخر، مرورکننده یک فرض را تغییر دهد و ارائه‌دهنده توضیح دهد کدام invariant نیاز به طراحی یا آزمایش تازه دارد.

در هر بخش ابتدا مسئله، سپس محل تصمیم، یک گزینهٔ کنارگذاشته‌شده، رفتار در خرابی و شاهد دقیق را نشان بده. مرز «پاسخ نامعلوم»، «اثر ثبت‌شده» و «وضعیت جاری» را با هم یکی نکن. شمارش تست‌ها، امضای بسته یا تعداد ریپو جای توضیح مستقل تصمیم را نمی‌گیرد. اجرای تازهٔ آزمایش‌ها و آماده‌سازی سرویس‌ها بخشی از این برنامهٔ ۳۰دقیقه‌ای نیست.
