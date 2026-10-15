# Codex CLI and Claude Code benchmark

Times include CLI startup, model and tool work, cleanup, event parsing, and external acceptance. Medians use PASS attempts only. Ratios require three PASS attempts from both clients. Text PASS checks formal requirements. Human style acceptance remains open.

## 2026-10-15-clean

Recorded attempts: 30. Excluded preparation incidents: 0.

| Client | PASS / eligible | Total attempted seconds | CLI seconds | External check seconds | First tool median seconds (n) |
| --- | --- | --- | --- | --- | --- |
| codex | 15/15 | 956.66 | 951.57 | 5.08 | 6.85 (15) |
| claude | 12/15 | 677.40 | 674.09 | 3.28 | 3.41 (15) |

Totals include failed and timed-out eligible attempts. Preparation incidents are reported separately and are not counted as model failures.

| Mode / task | Codex: PASS; median [min-max] s | Codex failures | Claude: PASS; median [min-max] s | Claude failures | Faster with 3/3 PASS |
| --- | --- | --- | --- | --- | --- |
| controlled / Go | 3/3; 107.56 [88.89-128.73] | - | 0/3; unavailable | tests: 3 | - |
| controlled / Python | 3/3; 79.54 [78.14-85.42] | - | 3/3; 57.03 [52.35-57.88] | - | Claude x1.39 |
| controlled / Editing | 3/3; 48.24 [46.77-48.62] | - | 3/3; 50.82 [44.14-57.62] | - | Codex x1.05 |
| controlled / Writing | 3/3; 60.84 [52.66-61.68] | - | 3/3; 47.03 [40.64-49.51] | - | Claude x1.29 |
| controlled / Text search | 3/3; 23.56 [20.70-25.33] | - | 3/3; 18.53 [17.26-24.36] | - | Claude x1.27 |

### Failed and excluded attempts

| Run | Outcome | Failed checks / recorded reason | Seconds |
| --- | --- | --- | --- |
| 03-controlled-go-r3-claude | tests | TestAcceptance/zero-limit | 57.92 |
| 11-controlled-go-r2-claude | tests | TestAcceptance/blank; TestAcceptance/zero-limit | 48.75 |
| 19-controlled-go-r1-claude | tests | TestAcceptance/zero-limit | 53.53 |

## 2026-10-15-original

Recorded attempts: 60. Excluded preparation incidents: 2.

| Client | PASS / eligible | Total attempted seconds | CLI seconds | External check seconds | First tool median seconds (n) |
| --- | --- | --- | --- | --- | --- |
| codex | 29/29 | 1843.95 | 1836.83 | 7.09 | 7.86 (29) |
| claude | 22/29 | 4473.32 | 4465.68 | 7.52 | 6.67 (29) |

Totals include failed and timed-out eligible attempts. Preparation incidents are reported separately and are not counted as model failures.

| Mode / task | Codex: PASS; median [min-max] s | Codex failures | Claude: PASS; median [min-max] s | Claude failures | Faster with 3/3 PASS |
| --- | --- | --- | --- | --- | --- |
| controlled / Go | 2/2; 98.47 [92.21-104.73] | excluded: 1 | 1/2; 122.82 [122.82-122.82] | excluded: 1, tests: 1 | - |
| controlled / Python | 3/3; 84.82 [64.73-91.14] | - | 3/3; 134.69 [121.85-175.77] | - | Codex x1.59 |
| controlled / Editing | 3/3; 50.96 [47.41-51.44] | - | 3/3; 68.38 [50.61-126.22] | - | Codex x1.34 |
| controlled / Writing | 3/3; 53.91 [50.71-59.24] | - | 3/3; 149.43 [41.68-177.86] | - | Codex x2.77 |
| controlled / Text search | 3/3; 19.24 [17.62-25.48] | - | 3/3; 22.77 [22.22-22.83] | - | Codex x1.18 |
| native / Go | 3/3; 82.20 [79.15-110.77] | - | 0/3; unavailable | tests: 3, timeout: 1 | - |
| native / Python | 3/3; 81.55 [78.76-95.48] | - | 2/3; 209.67 [155.19-264.15] | timeout: 1 | - |
| native / Editing | 3/3; 83.41 [58.58-83.59] | - | 3/3; 241.77 [103.86-258.21] | - | Codex x2.90 |
| native / Writing | 3/3; 63.46 [56.34-67.19] | - | 1/3; 235.95 [235.95-235.95] | timeout: 2 | - |
| native / Text search | 3/3; 32.58 [24.23-33.01] | - | 3/3; 43.43 [30.54-45.74] | - | Codex x1.33 |

### Failed and excluded attempts

| Run | Outcome | Failed checks / recorded reason | Seconds |
| --- | --- | --- | --- |
| 03-controlled-go-r2-claude | excluded | Excluded: accidental real CLI launch during fake qualification before protocol fixes | 162.08 |
| 04-controlled-go-r2-codex | excluded | Excluded: accidental real CLI launch during fake qualification before protocol fixes | not recorded |
| 07-native-write-r3-claude | timeout |  | 301.31 |
| 10-native-write-r1-claude | timeout |  | 301.52 |
| 14-controlled-go-r3-claude | tests | TestAcceptance/blank; TestAcceptance/zero-limit | 116.63 |
| 18-native-go-r3-claude | tests | TestAcceptance/blank; TestAcceptance/zero-limit | 288.48 |
| 19-native-python-r3-claude | timeout |  | 301.72 |
| 47-native-go-r2-claude | timeout + tests | TestAcceptance/blank; TestAcceptance/zero-limit | 303.16 |
| 50-native-go-r1-claude | tests | TestAcceptance/blank | 244.50 |

## Limits

Original and clean series have different advisor and extension policies. The clean series uses high effort for both clients. Original native Claude uses xhigh. Separate system prompts and tools remain. Effort names are not equivalent across providers. Three repetitions do not establish statistical significance. Server cache and background machine load are not isolated. Codex model identity is requested, not independently verified backend identity. First-event timing is not TTFT. Missing measurements are unavailable, not zero. Generation TPS is unavailable.
