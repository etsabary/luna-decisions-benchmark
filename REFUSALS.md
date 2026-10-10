# Persistent refusal observations

17 of the 1,000 primary questions ended in HTTP 502. The exact body, preserved in the attempt error message, was:

```json
{"error":{"message":"OpenAI refused to answer question \"decision\"","code":502}}
```

These are API errors with no choice, confidence, probabilities or usage fields. They are distinct from low-confidence answers and wrong valid decisions. Error responses do not identify the dated underlying model; all valid responses in the same requested-model run identified the October 6 Luna Decisions snapshot.

Each affected item failed on both original attempts and all three separately recorded follow-up attempts: **85 refusals across 17 items**, five per item, with zero recovered answers. This persistence argues against a one-off transient recovery in this session, but does not establish the underlying cause. The message alone is insufficient to label the event a safety refusal or inability to solve a puzzle.

| Item ID | Family | Question | Primary calls | Follow-up calls | Recovered? |
|---|---|---|---:|---:|---|
| J000194 | Forward conditional reasoning | Which of the five named flags must be on? | 2 | 3 | No |
| J000218 | Forward conditional reasoning | Which of the five named flags must be on? | 2 | 3 | No |
| J000225 | Forward conditional reasoning | Which of the five named flags must be on? | 2 | 3 | No |
| J000233 | Forward conditional reasoning | Which of the five named flags must be on? | 2 | 3 | No |
| J000853 | Scheduling constraints | On which day does Dion present? | 2 | 3 | No |
| J000854 | Scheduling constraints | On which day does Dion present? | 2 | 3 | No |
| J000906 | One-to-one assignments | Which answer correctly describes Wren's locker assignment? | 2 | 3 | No |
| J000935 | One-to-one assignments | What can be concluded about the locker used by Uma, considering all the clues? | 2 | 3 | No |
| J000945 | One-to-one assignments | Which answer correctly describes Luz's locker assignment? | 2 | 3 | No |
| J000953 | One-to-one assignments | Which answer correctly describes Ava's locker assignment? | 2 | 3 | No |
| J000981 | One-to-one assignments | Which answer correctly describes Tess's locker assignment? | 2 | 3 | No |
| J001002 | One-to-one assignments | Which answer correctly describes Galen's locker assignment? | 2 | 3 | No |
| J001462 | Object tracking through swaps | Which box contains the green token after all the steps? | 2 | 3 | No |
| J001818 | Verbal spatial tracking | Where is the robot relative to its starting point? | 2 | 3 | No |
| J001832 | Verbal spatial tracking | Where is the robot relative to its starting point? | 2 | 3 | No |
| J002153 | Perspective and belief tracking | In which room does Ravi believe the key is now? | 2 | 3 | No |
| J003177 | Deterministic fault diagnosis | Which component is faulty? | 2 | 3 | No |

Full facts and choices are in `data/questions_1000.csv`, indexed by item ID. Original outcomes are in `data/results_luna_1000.csv`; follow-up outcomes are in `data/results_luna_refusal_followup.csv`. Every HTTP attempt and UTC timestamp is retained in the two `attempts_luna_*.jsonl` files. The primary run's 61.2% attempted accuracy and 62.3% answered accuracy are unchanged after the follow-up.

No refusal attempt returned billing information. Missing usage/cost must not be treated as confirmed zero charge. The original and follow-up manifests document retry bounds and input identity. Further tests could compare a direct OpenAI call and a newly recorded run after an API update; neither was performed in this experiment.


## Slow request-rate control test (additional experiment)

To investigate rate limiting, a later diagnostic used one worker, no retries,
and at least three seconds between request starts (at most 20 starts/minute).
It selected the lexicographically first refused item from each of the seven
affected families and alternated each with a previously answered item of the
same family and difficulty level. Control selection preferred the same role and
variant, then the closest context word count; it used no gold answers.

**All seven previously refused items returned the same HTTP 502 refusal again;
all seven controls returned valid decisions**, with the same dated Luna snapshot
as the primary successful responses. The original payloads were unchanged.
This makes ordinary request-rate throttling less plausible in this session,
but does not exclude a request-dependent backend bug, cached errors or other
undisclosed provider behavior.

Paid requests can still encounter upstream rate limits. OpenRouter's
[rate-limit documentation](https://github.com/OpenRouterTeam/docs/blob/main/api_reference/limits.mdx)
describes provider-side throttling; its
[error documentation](https://github.com/OpenRouterTeam/docs/blob/main/api_reference/errors-and-debugging.mdx)
normally distinguishes HTTP 429 rate limits from HTTP 502 provider failures.
These general error categories alone cannot diagnose this alpha endpoint.

The diagnostic is separate from the primary run and the three-attempt follow-up.
It adds one further refusal attempt for seven of the original 17 items and seven
successful control calls; it changes neither primary choices nor primary scores.
See `data/slow_rate_diagnostic_manifest.json`,
`data/slow_rate_diagnostic_attempts.jsonl`,
`analysis/refusal_diagnostics.json` and `diagnose_refusals.py`.

## What stands out in the question content

- Six refusals are one-to-one locker assignments and four are forward implication
  chains. Those two families account for 10/17 refusals, while other questions
  using the same templates succeeded.
- Refusals occur at every difficulty level: four at level 1, three at level 2,
  three at level 3 and seven at level 4. Difficulty alone does not explain them.
- Some are especially simple: J001462 asks about a token unaffected by either
  swap, J001818 describes only turns without movement, and J002153 queries a
  person's belief even though that person observes none of the later moves.
  These involve retaining an unchanged state, but many other refused items do
  not, so that is a possible sub-pattern rather than a unifying explanation.
- Two pairs preserve the same underlying problem: J000218/J000225 add irrelevant
  background text, and J000853/J000854 rotate option order. Both members of each
  pair refused. Harmless wording or option-position differences did not recover
  those cases in the original run.
- Successful primary decisions included reported confidence as low as 0.02;
  94 successful decisions had confidence below 0.1. A blanket low-confidence
  cutoff therefore does not explain why these items produced errors.

There is no obvious common sensitive subject. The leading working hypothesis is
input-dependent model or native-decision adapter behavior. Internal abstention,
validation behavior, and cached or deterministic backend errors remain possible;
the available responses cannot distinguish them. This is a hypothesis, not an
identified defect or proof of a safety policy. A direct OpenAI comparison or an
independently recorded later rerun would be useful next tests.
