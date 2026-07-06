# Catching project risks before they blow up: an AI monitoring workflow

Usman · July 2026

## The problem I'm trying to solve

Projects rarely fail suddenly. The warning signs are almost always sitting in plain sight, scattered across ticket comments and standup notes: a due date that quietly slips twice, someone writing "still waiting on the API team" three days in a row, a casual "we might need legal to look at this." No single update looks alarming, so nobody acts. By the time the pattern is obvious, it's a fire.

The idea here is a workflow that reads those routine updates for you, picks out signals of risk, dependencies, and blockers, and puts them in front of the right person early. It flags — it doesn't act. PMs stay in charge of decisions; the system just makes sure nothing important gets skimmed past.

## What it watches

Two kinds of input, deliberately different in shape:

1. Jira-style tickets — structured stuff: status changes, due dates, assignees, comments, blocker links.  
2. Standup or status notes — free text, one short update per person per day.

The structured data is good at catching *slippage* (dates moving, tickets sitting in "Blocked"). The free text is where the human signals live — hedging, frustration, mentions of things nobody made a ticket for. You want both, because teams routinely say things in standups that never make it into Jira.

For the prototype I'd use entirely made-up data: around 50 tickets and 60 standup entries across three fictional teams, with roughly 15 problems deliberately planted in there (a ticket blocked for four days, a dependency chain where the upstream item is late, a slip nobody mentions out loud). Planting the problems myself means I get ground truth for free — I know exactly what the system should have caught, so I can measure it honestly.

## How it works

```
flowchart LR
    A[Tickets] --> C[Normalize]
    B[Standups] --> C
    C --> D[Rules pass]
    D --> E[LLM pass]
    E --> F[Score + dedup]
    F --> G[Dashboard + alerts]
    G --> H[PM confirms or dismisses]
    H --> F
```

**First, normalize everything.** Every incoming update — ticket comment, status change, standup line — gets converted into the same simple record: who, when, which project, what text, plus any structured fields. Everything downstream is source-agnostic, which keeps the code small.

**Then a cheap rules pass.** Before any AI gets involved, plain old rules catch the obvious cases: a due date that's moved more than once, a ticket sitting in Blocked for days, an in-progress ticket with no activity all week, text containing phrases like "waiting on" or "blocked by" or "might slip." This is boring and that's the point — it's free, instant, deterministic, and honestly catches most of what matters. It also means the demo runs with no API key at all.

**Then the LLM pass, on candidates only.** Updates the rules flagged (plus a small random sample of ones they didn't, to see what the rules miss) go to an LLM — something cheap like Claude Haiku works fine. It returns one structured judgment per update: is this a risk, a dependency, or a blocker; a one-line summary; who's blocked on whom; a severity; and — this part I care about most — **an exact quote from the update as evidence**. If the model can't point to the actual words, it has to return "none." That one constraint does most of the work of keeping hallucinated signals out, and it makes triage fast: the PM reads the quote and knows in five seconds whether the flag is real.

The prompt also gets the ticket's structured context (due date history, status changes), so the model can reason about slippage rather than just tone.

**Then scoring and dedup.** Raw flags aren't useful; ranked ones are. Priority is basically severity × confidence, with two adjustments I think matter a lot:

- Repetition beats intensity. The same dependency mentioned in three different standups should outrank one dramatic comment. That's how real slippage actually shows up — quietly, repeatedly.  
- Related signals get merged. Five updates about the same blocker become one card with five quotes attached, not five alerts.

There's also a small dependency graph built from extracted "X depends on Y" pairs. When an upstream item is late, everything downstream gets flagged — which catches cascade risks that no single update ever states explicitly.

**Finally, the outputs.** A Streamlit dashboard with signal cards sorted by priority (evidence quotes, linked items, filters by project and type), plus alerts: high-severity goes straight to the project owner on Slack, everything else lands in a daily digest. Each card has confirm / dismiss / snooze buttons. Dismissals get logged and feed back into the thresholds — that feedback loop is what makes precision improve over time instead of decaying.

## What counts as what

I'm using three categories, and the distinction is about time:

- **Blocker** — work is stopped *right now*. "Can't test until staging is fixed."  
- **Dependency** — work *will* need something that isn't secured yet. "This needs the auth service, which ships next sprint."  
- **Risk** — nothing's stopped, but the odds of trouble are rising. Two date slips plus hedging language in standups.

Severity is high if a sprint goal or multiple downstream items are threatened, medium if one item's at risk but there's a workaround, low if it's just worth watching.

## Stack

Nothing exotic: Python for the pipeline, SQLite for storage, Streamlit (Community Cloud or a Hugging Face Space) for the dashboard, a Slack webhook for alerts, and a cron job or GitHub Action polling every 15 minutes. The LLM call sits behind a single `classify(update)` function, so the prototype can run on heuristics alone and the real API call drops in later without touching anything else.

## Choices I'd defend

**Rules first, LLM second — not LLM on everything.** It cuts API cost by well over half, the easy cases get deterministic handling, and the pipeline keeps working if the API is down. The cost is that clever phrasing can slip past the rules, which is why a sample of unflagged updates goes to the LLM too — whatever it finds there becomes a new rule.

**Every flag must quote its source.** Non-negotiable. Trust in an early-warning system evaporates after a few unverifiable alerts.

**No auto-actions.** The system never changes a ticket or pings an executive on its own. False alarms that trigger real consequences are how these tools get turned off.

## Ways it fails, and what I'd do about them

Alert fatigue is the big one — handled by confidence thresholds, digest batching, and tuning off the dismiss data. The sneakier failure is *silence*: a struggling ticket where nobody says anything. So silence itself is a signal — in-progress work with no updates for X days gets flagged. There's also the "all good\!" problem, where someone masks trouble with cheerful updates; that's why the structured signals (dates, status history) are scored independently of text tone. Malformed LLM output gets schema-validated and retried, falling back to the rule-based label. And the prototype only ever touches synthetic data — a production version would need a properly access-controlled environment with redaction at ingestion.

## How I'd know it works

Against the planted problems in the dummy data: did it catch them (recall), and how much junk came with them (precision)? I'd want recall around 0.85 or better at this stage, precision at least 0.7. The metric I find most interesting is lead time — how many days before the planted "incident" did the first flag appear? Early is the whole point. In production, the confirm-vs-dismiss rate from PMs becomes the ongoing precision measure.

## Build order (fits in about an hour)

Generate the synthetic dataset with planted problems (\~10 min). Write the rules pass and scoring, maybe 100 lines of Python (\~15 min). Stub the LLM stage behind the `classify()` interface (\~10 min). Streamlit dashboard with priority-sorted cards (\~15 min). Run the eval against the planted signals and write down the numbers (\~10 min).

After that, the obvious v2 items: real Jira and Slack connectors, live LLM calls with few-shot examples tuned from dismiss data, a proper dependency graph view, and maybe meeting transcripts as a third input.  
