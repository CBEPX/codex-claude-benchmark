# Codex CLI and Claude Code task benchmark

This repository contains two benchmark datasets from 2026-10-15 and a portable runner.
The tasks cover Go, Python, Russian text editing, Russian technical writing, and text search.
Each client receives a fresh copy of the same task.
External checks evaluate the result after the client exits.

The repository supports two separate operations:

1. Verify the archived evidence and rebuild its reports without model requests.
2. Run a new benchmark with your own authenticated CLI installations.

## Recorded results

The latest clean series disables Claude's built-in advisor and user extensions.
Both clients use `high` effort.

| Task | Codex PASS · median seconds | Claude PASS · median seconds |
| --- | --- | --- |
| Go | 3/3 · 107.56 | 0/3 · unavailable |
| Python | 3/3 · 79.54 | 3/3 · 57.03 |
| Editing | 3/3 · 48.24 | 3/3 · 50.82 |
| Writing | 3/3 · 60.84 | 3/3 · 47.03 |
| Text search | 3/3 · 23.56 | 3/3 · 18.53 |

Codex passed 15/15 attempts. Claude passed 12/15 attempts.
The clean series had no CLI timeouts and no recorded advisor calls.
Claude failed `TestAcceptance/zero-limit` in all three Go attempts.
One attempt also failed `TestAcceptance/blank`.

Total attempted time was **956.66 seconds for Codex** and **677.40 seconds for Claude**.
These totals include failed attempts and external checks.
They do not represent equal successful completion because Claude failed the three Go tasks.
For the other 12 paired PASS attempts, totals were 631.49 and 517.19 seconds.

The original series contains 60 accounted attempts across native and controlled modes.
Two preparation incidents are excluded from model comparisons.
Of the 58 eligible attempts, Codex passed 29/29 and Claude passed 22/29.
Claude had four test failures and four timeouts. One attempt belongs to both categories.

See [the complete tables](published/RESULTS.md) and [machine-readable summaries](published/summary.json).
The [HTML comparison](published/comparison.html) contains 18 blind A/B text pairs across both series.
Download that file and open it in a browser to view the comparisons.
GitHub's file viewer does not execute the HTML.

## Requirements

- Python 3.11 or later. CI uses Python 3.14.3.
- Go 1.27 or later. The fixed Go module requires Go 1.27. CI uses Go 1.27.2.
- Git and a POSIX system. CI checks macOS and Linux. Windows is not supported in this release.
- Codex CLI and Claude Code are required only for new real runs.

The historical manifests record Codex CLI `0.162.1` and Claude Code `2.1.300`.
The requested models are `gpt-6.1-sol` and `claude-opus-5-5`.
Original native Claude uses `xhigh`. Other historical cohorts use `high`.
The portable runner defaults to the clean `high` profile for both clients.

New runs record the actual installed CLI versions.
The runner does not install clients, change models automatically, or start interactive login.
Provider model availability and supported CLI flags can change.
An incompatible client or failed isolation probe stops the run.

## Verify the archive without model requests

```sh
git clone https://github.com/CBEPX/codex-claude-benchmark.git
cd codex-claude-benchmark
git checkout v0.1.0
python3 -m unittest discover -s tests -v
python3 benchmark.py verify --dataset all
python3 benchmark.py report --dataset all --output-dir reports
```

The tests use explicit fake client executables. They do not call model APIs.
`verify` checks public file hashes and replays acceptance checks against stored model solutions.
It expects the recorded model failures. A matching historical failure is a successful integrity check.
There are 88 eligible solutions to replay and two separately recorded preparation incidents.
All replay work happens in temporary directories.

Open `reports/comparison.html` to compare the texts.
`reports/RESULTS.md` contains per-task tables, exact failed test names, totals, and latency coverage.
`reports/summary.json` contains numeric summaries.

To select one series, replace `all` with `2026-10-15-clean` or `2026-10-15-original`.

## Run a new clean series

Authenticate both CLIs in your own terminal before you start.
Check the selected installations:

```sh
codex --version
claude --version
```

Start a new run in a directory that does not exist:

```sh
python3 benchmark.py run --real --output-dir runs/my-run
```

A full run makes two short, unscored isolation probes and 30 scored CLI launches.
It uses your provider accounts and their applicable usage limits.
Each client receives five tasks, with three repetitions per task.
The fixed schedule uses seed `20261015` and alternates which client runs first.
The clients run sequentially, with fresh sessions and task copies.

The CLI deadline is 300 seconds per scored attempt.
Process cleanup and external acceptance can add time after that deadline.
The runner does not retry a failed or timed-out attempt.

To check isolation without a scored series:

```sh
python3 benchmark.py run --real --probe-only --output-dir runs/isolation-check
```

To select other installed binaries or models explicitly:

```sh
python3 benchmark.py run --real --output-dir runs/another-model-run \
  --codex-bin /path/to/codex --claude-bin /path/to/claude \
  --codex-model MODEL --claude-model MODEL --effort high
```

Those settings define a new experiment. They do not recreate the historical environment.
The runner records the binaries, versions, models, source hashes, and input hashes.
Claude assistant events must match the requested model.
Codex backend identity remains unverified. Its identity is recorded as requested.

## Isolation and interrupted runs

Codex uses a dedicated `CODEX_HOME` with hooks, memories, apps, plugins, host skill discovery, and project instruction discovery disabled.
The runner references the existing Codex auth file through a temporary local symlink.
It removes that link on normal completion and handled setup or run errors.
It does not copy credentials into the dataset.

Claude uses safe mode, empty setting sources, disabled hooks and user plugins, and an empty strict MCP configuration.
Its tools are Bash, Read, Write, Edit, Glob, and Grep.
The child process receives `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1`.
That switch was verified for the recorded Claude Code version. Future versions require a successful preflight.

An advisor call, helper model, forbidden extension, or failed context check stops further launches.
The stop condition persists across resume.
A timeout without a final event cannot receive PASS. It does not itself prove advisor interference.

Resume only the same configuration:

```sh
python3 benchmark.py run --real --resume --output-dir runs/my-run
```

Recorded attempts and completed probes are not repeated.
An unfinished attempt directory without a result requires manual audit.
The runner stops there because it cannot prove whether a model request already ran.
A changed runner, input, configuration, or CLI version also blocks resume.
The process supervisor checks observed descendants by PID and process-start identity.
It cannot prove coverage of an unobserved short-lived double-fork descendant.

## Data layout and provenance

- `fixtures/` contains the fixed task prompts, inputs, and visible tests.
- `oracle/` contains external tests, expected text/search constraints, and reference solutions.
- `datasets/` contains both series, per-attempt solutions, public event traces, acceptance logs, and metadata.
- Each dataset has `public-manifest.json`, `source-provenance.json`, and `redactions.json`.
- `snapshots/` inside each dataset contains historical source snapshots as non-executable text files.
- `published/` contains deterministic reports generated from the public datasets.
- `runs/`, `reports/`, and `.work/` are ignored local output directories.

Public traces are filtered evidence, not unchanged raw session logs.
They omit account data, quota details, request/session identifiers, native instructions, reasoning, and tool input/output bodies.
Standalone model solutions and external acceptance logs are retained.
Home paths, private URLs, private hostnames, email addresses, and UUIDs are redacted where necessary.
The original private archives remain unchanged.

Original source hashes commit to the original bytes.
Public manifests hash the exported bytes after filtering.
These hashes serve different purposes. A redacted file is not expected to match its original source hash.
The exporter verifies source manifests before export.

To export a new run for local review:

```sh
python3 benchmark.py export --source runs/my-run \
  --dataset my-reviewed-run --output-dir reviewed/my-reviewed-run
```

Inspect that export and run a secret scan before you publish it.
The exporter does not upload anything.
Never publish a raw run directory or an auth/config directory.

## Timing definitions

`client_seconds` measures CLI launch through process cleanup.
`validation_seconds` measures the external acceptance phase.
`total_seconds` uses one monotonic interval through cleanup, parsing, context checks, and acceptance.
It includes the initial wait after the request.
Preparation before CLI launch is outside that interval.

New runs also store `events-timing.jsonl` with monotonic event receipt offsets.
`first_activity_seconds` marks the first recorded assistant text or tool call.
`first_tool_seconds` marks the first recorded tool call.
Initialization messages and reasoning records are not counted as assistant activity.
These measurements concern complete recorded events. They are not exact first-token latency or generation TPS.

Historical latency was reconstructed from matching session/event timestamps after the series.
Its basis is `source_event_timestamp`, not the new monotonic receipt basis.
The dataset records coverage and the supporting first-event timestamps.
Unavailable measurements remain null.

## Interpretation limits

Three repetitions do not establish statistical significance.
The clients have different system prompts, tools, reasoning implementations, and cache behavior.
An effort label such as `high` is not equivalent across providers.
Fresh sessions do not guarantee a cold server cache.
Background machine load was not isolated. The recorded load averages are retained.

The clean series changes advisor and extension settings together.
It does not isolate the causal effect of advisor alone.
The original native extension environment is historical evidence, not a portable default.
Private instruction contexts were not published, so exact reconstruction of that native environment is unavailable.

External tests are public and applied outside model working copies.
The prompts prohibit network access, delegation, and work outside the task directory.
This is a cooperative task benchmark, not a contamination-proof adversarial evaluation.
Text acceptance checks protected facts, structure, required commands, and length. It does not assess style automatically.
Prose checks do not prove that every additional sentence preserves meaning or avoids new facts.

## License

The benchmark code and synthetic materials use the [MIT License](LICENSE).
Codex CLI and Claude Code are separate products. Their binaries, credentials, and native instruction contexts are not redistributed.
