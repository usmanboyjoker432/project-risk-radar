# Project Risk Radar

A small AI workflow that reads routine project updates — Jira-style tickets and daily standup notes — and flags risks, dependencies, and blockers before they escalate. Built as a \~1 hour prototype on fully synthetic data. It flags, it doesn't act: a PM confirms or dismisses every signal.

See `ai-risk-monitoring-workflow-design.md` for the full design rationale.

## How it works

Every update (ticket status change, comment, standup line) is normalized into one common shape, then passed through three stages:

1. **Rules pass** — deterministic checks catch the obvious: due dates that moved twice, tickets sitting in Blocked for days, in-progress work gone silent, overdue upstream items in a dependency chain, and phrase families like "waiting on" / "depends on" / "might slip".  
2. **Classification** — the `classify()` function in `pipeline.py` labels each candidate with a type (blocker / dependency / risk), severity, confidence, and an evidence quote. Today it's rule-based, so the demo runs with no API key. This function is the LLM seam: swap its body for a Claude API call returning the same dict and nothing else in the codebase changes.  
3. **Scoring & dedup** — related signals merge into one card per ticket (or per person+topic for standups). Priority \= severity × confidence × a repetition boost, because the same dependency mentioned in three standups matters more than one dramatic comment.

## Running it

```shell
python3 -m pip install streamlit pandas
python3 data_gen.py                  # generates tickets.json, standups.csv, planted.json
python3 pipeline.py                  # prints ranked signals to the terminal
python3 eval.py                      # scores detection against ground truth
python3 -m streamlit run app.py      # opens the dashboard
```

## The dashboard (`app.py`)

A Streamlit app showing every detected signal as a card, sorted by priority. High-severity cards come pre-expanded. Each card shows the evidence quotes (exact text from the source update — every flag must cite its source), the signal type, severity, confidence, and owner, plus confirm / dismiss / snooze buttons that stand in for the human triage loop. The sidebar filters by signal type, severity, and team, and a metrics row up top counts blockers, dependencies, and risks currently in view.

## The eval harness (`eval.py`)

The synthetic dataset isn't just filler — `data_gen.py` plants 15 known problems (stuck-in-Blocked tickets, double date slips, silent tickets, a dependency chain with a late upstream item, and repeated "waiting on..." standup lines) and records them in `planted.json` as ground truth. `eval.py` runs the pipeline and checks every planted signal against the produced cards: planted tickets match by ticket ID, planted standup signals match by their evidence phrase. It reports recall (planted signals caught), precision (cards that aren't false alarms), and lists anything missed.

Current results on the generated dataset:

```
Recall:    1.00  (15/15 planted signals caught)
Precision: 1.00  (0 false-positive cards)
```

A perfect score here says the rules cover the planted patterns, not that the system is done — real project language is messier, which is exactly what the LLM stage is for. The harness exists so that swap can be measured instead of guessed at.

## Files

- `data_gen.py` — builds the synthetic dataset (52 tickets, 65 standups, 15 planted problems)  
- `pipeline.py` — normalization, rules, `classify()` seam, scoring, dedup  
- `app.py` — Streamlit dashboard  
- `eval.py` — precision/recall against `planted.json`  
- `ai-risk-monitoring-workflow-design.md` — design doc

## What v2 would add

Live Jira and Slack connectors instead of files, real Claude API calls in `classify()` with few-shot examples tuned from dismiss data, Slack alerts (immediate for high severity, daily digest otherwise), a proper dependency-graph view, and threshold learning from the confirm/dismiss feedback.  
