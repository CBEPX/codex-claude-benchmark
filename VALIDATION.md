# Release validation

This record describes the publication checks on 2026-10-15.
It separates archived evidence, local tests, and real CLI qualification.

## Archived evidence

- The repository contains 90 accounted historical attempts in two separate series.
- Offline acceptance replay matches all 88 eligible solutions, including the recorded failures.
- Two preparation incidents remain visible and excluded from model comparisons.
- The deterministic reports contain 18 blind A/B text pairs.
- Original source archives retain their original hashes. Public manifests describe the filtered export.

The clean-series totals remain 956.6570197100227 seconds for Codex and 677.3952603760117 seconds for Claude.
Codex passed 15/15 clean attempts. Claude passed 12/15.
No historical model series was repeated for publication.

The Go `zero-limit` requirement is ambiguous in the original prompt.
The fixed test requires an error for `maxBytes=0`, but the prompt does not state that outcome explicitly.
Two clean Claude Go attempts failed only that case. The third also failed `blank`.
Recorded acceptance failures remain intact. They do not establish general Go capability.

## Review and regression checks

One independent review found three Important issues and no Critical or Minor issues.
Regression tests reproduced each issue before the fixes:

1. Unverified CLI or acceptance-process cleanup now stops further launches and resume.
2. Missing code artifacts produce acceptance failures. Result-processing errors preserve the failed attempt and stop further launches.
3. Historical Claude first-activity reconstruction excludes thinking-only events.

The latency correction changes the original-series Claude first-activity median from 6.012314 to 6.673976 seconds.
It does not change first-tool measurements, total times, or acceptance outcomes.

The local suite contains 25 tests, including a complete 30-attempt fake-client run.
The tests do not call model APIs.
Privacy checks and Gitleaks report no findings in the publication package.
The CI workflow repeats offline checks on Linux and macOS and runs a separate secret scan.
CI results are available in the repository's Actions tab.

## Two real isolation probes

Exactly two unscored real CLI requests ran during publication: one per client.
Both returned `CLEAN_READY`, exited successfully, and passed observed-process cleanup.
These probes are not speed measurements and do not enter the historical tables.

- Claude passed qualification with no recorded advisor calls or hook events.
- Codex failed the context check because its initial profile still exposed the host user skill catalog.

The runner stopped after the Codex context failure. It started no scored series.
A regression test reproduced the profile omission.
The corrected profile explicitly disables discovered user and administrator skills by path.
The local `codex debug prompt-input` check then contained no user skill catalog or custom instruction markers.
That diagnostic renders prompt input without a model inference request.
The disable mechanism follows the [official Codex skills documentation](https://developers.openai.com/codex/skills).

No additional real Codex request ran after this correction.
The corrected profile therefore has local prompt evidence, not a second successful real qualification.
Every new real run must pass its own two-client preflight before scored requests can start.

The probes did not change the checked global configuration files.
The runner removed its temporary Codex auth link.
The [sanitized attestation](validation/isolation-smoke.json) records versions, process results, source hashes, and this qualification boundary.
Raw native contexts, account metadata, and credentials are not public artifacts.

## Supported proof boundaries

This is a cooperative task benchmark. Public acceptance tests are not a defense against hostile test spoofing.
The process supervisor covers observed descendants and checks stdout closure.
It cannot guarantee detection of an unobserved short-lived double-fork descendant.
Explicit fake executable paths are trusted operator input.
Human prose-quality assessment, equivalent provider effort, statistical significance, and Codex backend identity remain unverified.

## Artifact checksums

`SHA256SUMS` covers tracked release files except itself.
Run `shasum -a 256 -c SHA256SUMS` from the repository root on macOS.
Run `sha256sum --check SHA256SUMS` on Linux.
Git commit and tag hashes identify the complete repository revision.
