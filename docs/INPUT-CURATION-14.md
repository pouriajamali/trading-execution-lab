# Finite input-curation source delta

The previous thirteen-command draft required an already admitted local feed
before any restore, but did not contain an official signature-verification
command. `scripts/input02_sdk14_delta.py` prepares an explicit batch verify
between the six graph commands and six cold lock restores. The final audit uses
`--no-restore`, so it cannot silently add another restore to the command count.

The fixed allocation is six graph commands at 8 seconds each, one batch verify
at 30 seconds, six restores at 28 seconds each, and one audit at 24 seconds:
fourteen SDK commands and 270 seconds. Data/terminal work retains 30 seconds,
for the original 300-second subbudget. The 720-second job, 620-second controller,
600-second work stop, 4 GiB/CPU2/64-process limits, Linux swap0, 8 GiB workspace
and 1 MiB proof/receipt envelopes are unchanged. Curation must have its complete
300 seconds remaining inside that same original worker clock.

The helper resolves absolute paths supplied by the existing own bound worker;
it launches no processes and acquires no SDK or packages. It rejects wildcard,
duplicate, escaping or stream paths. Its private config clears inherited feeds
and fallback folders, requires signatures and preserves
`allowUntrustedRoot=false`. Repository certificate choices are restricted to
the exact official NuGet signing-history fingerprints already retained in
common4dab. The report parser requires exactly one ordered, successful,
canonical content hash per enumerated original archive and rejects every
warning/error/unknown revocation report. It does not compute a replacement
NuGet hash or independently declare PKI admission.

Previously successful 03 verifications may be reused only for the same
id/version/original raw identity, with their original signature, timestamp,
freshness and PKI scope preserved. An independent certificate/CRL result that
was `UNKNOWN` remains `UNKNOWN`. Different SQLite 10.0.14 and 10.0.15 inputs
cannot substitute for one another. Full raw/member/expanded/notices/advisory
data, current applicable trust evidence, actual own02 graph/locks/assets and
the existing current-host/caps/source checks are still required before this
plan can be executed or a feed can be admitted. The helper is not wired into
the product entrypoint as a shortcut around its missing-lock gate.

Local source checks: `python -I -B scripts/test_input_curation14.py`.
These are synthetic command/config/report tests and run no SDK or native job.
The new parser was also checked locally against the retained actual03
seventeen-package report without replaying its SDK commands.

On 2026-11-17 the owner prohibited GitHub Actions because the quota is exhausted.
CI was not run per owner instruction. The source-only topic commit uses
`[skip ci]`; workflow, protection, billing, tags and existing releases are
unchanged. No target SDK graph/restore, product build/test or new distributable
is established by this source delta. Runtime input closure and release remain
pending an actually admitted execution route and all original delivery gates.

## 18 November 2026 local delivery

Both native local platforms independently completed the 14-command factory with
strict official all/online verification of33 exact originals, six real two-RID
lock/asset restores and complete applicable current advisory audit. Linux used
signed existing locks in locked mode. No legacy independent-PKI UNKNOWN field is
relabeled. GitHub Actions remains forbidden; see the
[current release evidence](RELEASE-v0.6.0-preview.1.md) for the direct signed
preview delivery and experimental Windows support limitation.
