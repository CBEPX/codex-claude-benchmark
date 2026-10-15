# Acceptance audit: tasks-v2

This revision improves the acceptance rules for future runs. It does not replace historical scores.
The runner records `contract_version: tasks-v2` and hashes the prompts, acceptance files, and runner source before execution.
Keep results from different contracts in separate cohorts. A historical solution tested with v2 rules is a diagnostic, not a new model attempt.

See the [local qualification record](validation/tasks-v2.json) for check results and source hashes.

## Requirement coverage

| Task | Requirements checked | Evidence |
| --- | --- | --- |
| Go | Positive limit before reads, UTF-8 byte length, exact LF/CRLF boundaries, whitespace, exact IDs, order, duplicate validation, reader errors, no partial output | [Go requirement map](GO-CONTRACT.md), `oracle/acceptance_test.go` |
| Python | Header set and order, blank records, quoted fields, stripped values, identity, currency, kind, amount syntax, row length, malformed CSV | `test_empty`, `test_headers`, `test_whitespace`, `test_invalid_rows` |
| Python | Per-row half-up rounding, exact large sums, payment/refund, zero totals, Decimal output, unchanged global context | `test_round_each_half_up`, `test_types_and_currencies`, visible tests |
| Python | Equal duplicates after quantization, conflicting kind/currency/amount | `test_duplicate`, `test_conflicting_duplicate` |
| Editing | Word count, protected fragments, known contradiction strings, numeric literals, no HTML comments, unchanged source | `engine.validate_prose`, `engine.validate_run` |
| Writing | Editing checks plus exact ordered level-two headings and standalone commands in the required sections | `engine.validate_prose`, `engine.validate_run` |
| Search | Twelve ordered answers, integer IDs and line numbers, exact values, current-source citations, missing-answer evidence, unchanged documents | `engine.validate_search`, `engine.validate_run` |

These are selected examples, not an exhaustive proof over all possible inputs.
Code tests assess observable behavior. They do not prove that an implementation never uses a forbidden internal operation such as `float`.
The benchmark assumes cooperative clients. It does not defend against deliberate test-output forgery.

## Reference and mutation qualification

A mutation is an intentional defect inserted into a reference solution.
The reference must pass. Each mutation must fail for a behavioral reason, not a syntax or build error.

The Go check rejects six defects: normalized IDs, character-based limits, rejection at the exact limit, accepted zero limits, premature reads, and insufficient CRLF capacity.
The Python check rejects five defects: fixed column order, ignored currency conflicts, ignored amount conflicts, unrounded duplicate comparison, and accepted Unicode digits.
All five Python defects passed the old acceptance suite before the new cases were added.

The new cases also exposed defects in the references.
The Go reference stripped a final bare CR, although v2 excludes only LF or CRLF from the byte limit.
The Python reference rejected large valid amounts at the default Decimal precision and leaked `csv.Error` from malformed headers.
The updated references pass these cases. The Python reference uses a local Decimal context.

Text mutation checks cover hidden instructions, invalid or duplicate sections, new numeric literals, extra commands, and changed commands.
Search checks include wrong values, wrong files, wrong numeric types, reordered answers, and incorrect missing-answer evidence.
The v2 prose and search rules are explicitly versioned. Historical replay retains the old rules.

Run the local checks without any model requests:

```sh
python3 -m unittest discover -s tests -v
python3 analyze_go.py
python3 benchmark.py verify --dataset all
```

The full suite includes a 30-attempt fake-client run through the runner and external acceptance.
Fake clients install reference artifacts. This checks integration, not model capability or speed.
The prose references are formal-check fixtures with repeated filler. They are not quality gold standards.

## Human review of prose

Automatic PASS means formal acceptance only. It does not establish semantic fidelity, useful transitions, or good writing.
A sentence can preserve every protected fragment and still add an unsupported requirement elsewhere.
Numeric checks compare digit sequences. They do not detect every change in units, signs, written-out numbers, or meaning.

Use the following rubric before revealing client names, timings, or automatic PASS values.

1. Select all editing and writing pairs in the cohort, including failed attempts and missing outputs.
2. Give two fluent Russian reviewers the original task, source facts, and A/B texts without client metadata.
3. Keep the A/B key with the coordinator. Do not give reviewers the repository, logs, or HTML reveal controls.
4. Record each review independently. Quote the output passage and source for each factual or procedural defect.
5. Record A, B, tie, or neither. Preserve disagreements before any discussion or adjudication.
6. Reveal the key after both reviews are fixed. Publish individual scores, disagreement counts, and any adjudication separately.

The existing HTML provides side-by-side texts, but it also contains reveal controls and the identity key.
A reviewer with that file can recover identities. It is not a secure blind-review package.
Prior knowledge of public outputs can also compromise blinding. Record that limitation for each reviewer.

| Criterion | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Factual fidelity | Contradiction, unsupported fact, or changed condition | Ambiguity with no established contradiction | All assessed claims follow from the source |
| Procedure, writing task | Incorrect command, transition, or stop behavior | Incomplete or unclear transition | Clear supported sequence and stop conditions |
| Editing task | Meaning lost or repetition increased | Some unnecessary repetition remains | Meaning preserved and repetition reduced |
| Clarity | Materially difficult to understand | Understandable with local ambiguity | Clear technical Russian for the stated reader |

Record a missing artifact as `missing`, not as a fabricated score.
Do not replace automatic PASS with a summed subjective score. Report the dimensions and pair preference separately.
No human scores are included in this revision. Future quality conclusions require completed reviews.

## Timing and interpretation

Keep failed attempts and timeouts in the outcome table. Report all-attempt time separately from matched successful-pair time.
Do not describe first complete event latency as token-level TTFT or infer generation speed from it.
Freeze the contract and schedule before either client starts. Do not adapt tests to favor an observed model result.
Three repeated runs remain an exploratory sample. They do not establish statistical significance or a general model ranking.
The [zero-limit sensitivity result](validation/go-sensitivity.json) is explicitly post-hoc and changes no historical timings or scores.
