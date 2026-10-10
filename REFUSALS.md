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
