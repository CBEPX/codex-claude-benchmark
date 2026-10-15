# Go contract v2 and test objectivity

New experiments record `contract_version: tasks-v2` in their manifest.
The archived datasets and v0.1.0 retain the original prompt, tests, scores, and timings.
Do not pool v2 measurements with the historical cohorts.

The original zero-limit prompt was ambiguous. Sol rejected `maxBytes <= 0` in all three clean Go solutions.
Claude rejected negative limits and treated zero as unlimited in all three solutions.
One Claude solution states that interpretation explicitly in its source comment.
These artifacts show different interpretations. They do not establish why either model chose its interpretation or a general capability difference.

Run `python3 analyze_go.py` to reproduce the separate historical sensitivity analysis.
It removes only the zero-limit case from a temporary copy of the original test suite.
It executes all six archived clean Go solutions and changes no historical artifacts or timing measurements.
The [stored result](validation/go-sensitivity.json) is a post-hoc diagnostic, not a new benchmark score.

## Explicit requirements and checks

| Requirement | Acceptance cases |
| --- | --- |
| Reject nonpositive limits before reading, including empty input | zero-limit, negative-limit-empty, zero-limit-data, no-read-0, no-read--1 |
| Measure UTF-8 bytes, allow exactly the limit | exact-limit, valid-over-limit, utf8-byte-limit, exact-crlf, bare-cr-counts, long record |
| Check length before skipping whitespace-only lines | blank, oversize-blank |
| Preserve exact ID and first occurrence | untrimmed-id, order, visible TestDeduplicate |
| Check duplicate records before deduplication | invalid-duplicate |
| Return no partial result on errors | invalid, reader error, partial reader failure |
| Accept large positive limits without eager allocation | maximum-limit-empty |

The new prompt defines whitespace through `strings.TrimSpace`, line endings, empty-result equivalence, and error-message freedom.
Assertions concern observable output and errors, not implementation structure.
The reference passes. Six intentional defects must fail: ID normalization, character counting, rejecting an exact limit, accepting zero, reading before rejecting a limit, and insufficient CRLF buffer capacity.
The original suite missed ID normalization, character counting, premature reads, and insufficient CRLF buffer capacity. The regression test reproduced those gaps before the acceptance changes.
This small mutation sample does not prove exhaustive coverage.

TRIZ triage: standard engineering applies. The defect is an implicit contract and missing cases, with no demonstrated technical contradiction.

## Remaining objectivity work

This change qualifies the observed Go defects. It does not certify every task family.
See [the full acceptance audit](OBJECTIVITY.md) for Python, prose, search, and the human review rubric.
No human quality scores or new model measurements accompany this change.
The next comparative run should freeze the revised protocol before either client sees it and report uncertainty across more repetitions.
