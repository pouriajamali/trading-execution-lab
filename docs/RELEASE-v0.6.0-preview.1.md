# v0.6.0-preview.1 â€” .NET 11 candidate

Candidate source updated 17 November 2026. Product builds and native tests are
still pending; no candidate tag, signed release assets or published download
exist. Signed source commits are separate from release-asset signing.

## Intended source changes

- Six managed projects target net11.0 with SDK 11.0.100, C# 15.0 and stable
  Core/ASP.NET framework floor 11.0.0. Patch-only runtime roll-forward;
  framework-dependent x64 Windows and Ubuntu 24.04/glibc packages.
- JWT authentication and TestHost use exact 11.0.0 references. SQLite 10.0.14,
  xUnit 4.0.2 and every frontend dependency remain pinned. SQLite's retained
  native graph still requires a fresh applicable audit and actual package proof.
- The launcher checks the exact selected x64 host and both stable 11.0
  frameworks before prompt/key/temp state. Controlled denials must finish with
  exit 1 and the prerequisite marker; infrastructure failure is INCOMPLETE.
- Two source-authored literal compatibility tests cover persisted receipt,
  fingerprint, wire shape and five-table schema. They are not historical binary
  captures and have not run. Original 57 C# cases and application sources remain
  unchanged; expected candidate count is 59, with zero execution results claimed.
- Tag CI stages a **draft**. Public release remains blocked until known-key
  signed checksums and actual bytes have been verified and authorized.

## Remaining technical gates

The consumer handshake now binds the supervisor-generated current instance to
the frozen admission fields and its exact own caps-evidence digest. The focused
10-case data checks cover this correction; they are not SDK or product tests.

Producer04's signed shared handoff now supplies accepted Linux and Windows
SDK histories and three actually verified Linux framework nupkgs. Own current
host, held kernel controls, ordinary dependency closure and product checks
remain mandatory. The supported hosted rows reuse these inputs; historical
local WSL/DrvFS failures are not a substitute for current native proof.

Generate all six real NuGet locks only with the admitted SDK, then review their
resolved/content-hash graph and current audit. No lock/native hashes are guessed
or copied from the old runtime. SDK selection, dependency compatibility, actual
loaded frameworks, native SQLite identities, resource caps and test outcomes
remain unverified. Project02 fixed-phase wrapper/guard source is now authored;
its actual producer input and kernel-control admission are still pending.

After admission, the complete execution contract requires the unchanged57 plus
two new C# cases, 11 protocol tests, 16 controlled launcher cases and existing22
matching-native extracted-package checks per OS. Timeouts, abnormal exits,
missing controls and infrastructure failures cannot count as negative passes.
No benchmark or performance claim is included.

## Exact publication route

1. Close the real package-input and six-lock gates, bind the complete signed
   source/tree and preserve the current supported-host and own-control checks.
2. The direct owner has authorized completing this existing upgrade through
   tests and preview publication. Use task-only signed pushes and the existing
   bounded source/tag pipeline; exact-source native tests and both package
   identities must pass before release publication.
3. Exact signed-tag CI must test both platforms and aggregate those same bytes,
   with no release rebuild. The workflow creates draft=true, prerelease=true.
4. The existing authorized key holder downloads the draft's three archives and
   SHA256SUMS.txt, verifies them, signs those exact sums in SSH namespace file,
   uploads SHA256SUMS.txt.sig and SIGNING-PUBLIC-KEY.pub and verifies actual draft
   bytes. The independent known fingerprint is
   SHA256:AgU5bZlJSjUu0KsWMmVEEr+BfXpcMVNroTA33bHcQdU, principal pouriajamali.
   No private key or new signing secret is introduced.
5. Publish only the exact authorized signed draft. Download all six public
   assets, verify signatures/hashes/manifest/source identities, execute actual
   extracted Windows/Linux downloads under admitted controls, and reopen the
   repository About/homepage/topics/README/release/download pages.

Retain the existing standard-runner timeouts: policy5 minutes, each native12
minutes with max-parallel1, release5 minutes. Proposed maximum is one source and
one tag workflow, <=63 runner wall-minutes and zero additional dollars, subject
to actual shared headroom before any trigger. Ordinary proof retention is3 days,
tag7 days. No account/billing/security/protection or old artifact changes.

## Existing public release

[v0.5.2-preview.1](https://github.com/pouriajamali/trading-execution-lab/releases/tag/v0.5.2-preview.1)
remains the published runtime with its original .NET10 prerequisites, signed
assets and historical56-case evidence. Later accepted M1 source has57-case
evidence. No old tag, asset, checksum, signature or historical measurement changes.
The public browser demo/site is independent and unchanged.

This is a synthetic local sample, not an exchange adapter, HA service,
network exactly-once guarantee, trading deployment or performance qualification.


## Shared SDK11 input and current consumer gates

The single common source is signed producer04 commit
`4dab824c2b0b6fe00858f648d07fd8e9df9fafe1`. Its unchanged data-only
`transport(rid, directory, context)` / `inspect_sdk(rid, root, context)` API
has actual accepted Linux and Windows histories. Those histories establish
input eligibility; each current Execution worker still needs its own source,
profile, held-process, kernel-limit and original-deadline evidence.

The [own route contract](SDK11-CONSUMER-CONTRACT.json) binds both per-RID
profiles and a complete source-pin table. The additional ordinary SQLite,
JWT, TestHost and xUnit closure, six real locks, full package signatures,
notices and current applicable advisory checks remain pending. No producer
kernel proof or old locks are borrowed. Existing .NET10 downloads remain the
available release until actual candidate tests, signing and publication pass.
The existing two native rows,720-second row,4GiB/CPU2/64-process limits and
620-second controller including transport and teardown remain unchanged.

Linux terminal capture retains the original nonroot ExecStopPost service result
before collection. A missing unit alone cannot pass: original held-worker and
launcher terminal proof, the generation-bound exit record and empty/absent own
cgroup are all required. Fresh project02 native evidence is still pending.

Native CI uses only a job-local Git autocrlf override so raw committed source
and shared input/proof hashes agree across Windows and Linux. No global Git
configuration or existing source line endings are changed.

The existing package process now has source wiring to record its actually loaded
CoreCLR and packaged SQLite module paths/hashes. This observation remains
unexecuted until the native product gate; installed-runtime inventory alone
does not establish which runtime the process loaded. Exact locked npm file-bin
links are allowed only inside node_modules; workspace escapes and directory
junctions remain denied. Windows includes the private SDK directory in the
same aggregate workspace/log limits as product work.


Input-curation source now includes a finite 14-command planning/report helper
with unchanged 300-second and native resource limits. See [the source delta](INPUT-CURATION-14.md).
The helper launches no SDK or product work; actual input closure remains pending.
CI was not run per the owner's 2026-11-17 instruction. No new release or binary
is claimed by this source-only [skip ci] change.
