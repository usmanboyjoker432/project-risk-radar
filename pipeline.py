"""Risk / dependency / blocker detection pipeline.

Stage 1: heuristic rules over normalized updates (structured + text).
Stage 2: classify() -- the LLM seam. Today it's rules; swap its body for a
         Claude API call returning the same dict and nothing else changes.
Stage 3: scoring, dedup into cards, priority ranking.
"""

import csv
import json
import re
from datetime import date

TODAY = date(2026, 7, 6)  # pinned so results match the generated dataset
SEV_WEIGHT = {"high": 3, "medium": 2, "low": 1}

TEXT_RULES = [
    ("blocker", "high", 0.8,
     r"\bblocked\b|\bwaiting on\b|\bstuck\b|can'?t (move|proceed|test)"),
    ("dependency", "medium", 0.7,
     r"\bdepends on\b|\bsign-?off\b|\bneeds? [a-z ]{0,30}(team|approval|legal)"),
    ("risk", "low", 0.6,
     r"\bmight slip\b|\bhopefully\b|\bnot sure\b|\brisk\b|\bscope grew\b"),
]


def days_ago(iso):
    y, m, d = map(int, iso.split("-"))
    return (TODAY - date(y, m, d)).days


def classify(text):
    """Classify one piece of update text. THE LLM SEAM.

    Replace this body with a Claude API call that returns the same shape:
    {"type": ..., "severity": ..., "confidence": ..., "evidence": exact quote}
    or None. Keep the rules as a fallback if the call fails.
    """
    for sig_type, severity, conf, pattern in TEXT_RULES:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return {"type": sig_type, "severity": severity,
                    "confidence": conf, "evidence": text.strip()}
    return None


def ticket_rules(t, by_id):
    """Structured checks on one ticket. Yields signal dicts."""
    sid = t["id"]

    if t["status"] == "Blocked":
        since = next((h["date"] for h in reversed(t["status_history"])
                      if h["status"] == "Blocked"), None)
        days = days_ago(since) if since else 0
        yield {"type": "blocker", "severity": "high" if days >= 3 else "medium",
               "confidence": 0.95,
               "evidence": f"Status has been Blocked for {days} days."}

    if len(t["due_date_history"]) >= 3:
        yield {"type": "risk", "severity": "medium", "confidence": 0.85,
               "evidence": f"Due date moved {len(t['due_date_history']) - 1} times."}

    if t["status"] == "In Progress" and days_ago(t["last_activity"]) >= 6:
        yield {"type": "risk", "severity": "medium", "confidence": 0.7,
               "evidence": f"No activity for {days_ago(t['last_activity'])} days "
                           "while In Progress (silence signal)."}

    if t["status"] != "Done" and days_ago(t["due_date"]) > 0:
        yield {"type": "risk", "severity": "high", "confidence": 0.9,
               "evidence": f"Overdue by {days_ago(t['due_date'])} days."}

    for up_id in t["blocked_by"]:
        up = by_id.get(up_id)
        if up and up["status"] != "Done":
            late = days_ago(up["due_date"]) > 0
            yield {"type": "dependency", "severity": "high" if late else "medium",
                   "confidence": 0.9,
                   "evidence": f"Depends on {up_id} ('{up['title']}'), which is "
                               + ("OVERDUE — cascade risk." if late else "not done yet.")}


def run_pipeline(tickets_path="tickets.json", standups_path="standups.csv"):
    """Returns cards sorted by priority (highest first)."""
    with open(tickets_path) as f:
        tickets = json.load(f)
    by_id = {t["id"]: t for t in tickets}
    raw = []

    # --- tickets: structured rules + text rules on comments
    for t in tickets:
        for s in ticket_rules(t, by_id):
            raw.append({**s, "key": t["id"], "team": t["team"],
                        "title": t["title"], "assignee": t["assignee"],
                        "source": "ticket"})
        for c in t["comments"]:
            s = classify(c["text"])
            if s:
                raw.append({**s, "key": t["id"], "team": t["team"],
                            "title": t["title"], "assignee": t["assignee"],
                            "source": "ticket comment"})

    # --- standups: text rules, deduped per author+type
    with open(standups_path) as f:
        for row in csv.DictReader(f):
            s = classify(row["text"])
            if s:
                raw.append({**s, "key": f"standup:{row['author']}:{s['type']}",
                            "team": row["team"], "title": f"Standup — {row['author']}",
                            "assignee": row["author"], "source": "standup"})

    # --- dedup into cards; repetition boosts priority
    cards = {}
    for s in raw:
        c = cards.setdefault(s["key"], {
            "key": s["key"], "team": s["team"], "title": s["title"],
            "assignee": s["assignee"], "type": s["type"],
            "severity": s["severity"], "confidence": s["confidence"],
            "evidence": []})
        c["evidence"].append(f"[{s['source']}] {s['evidence']}")
        # card takes the worst severity / highest confidence seen
        if SEV_WEIGHT[s["severity"]] > SEV_WEIGHT[c["severity"]]:
            c["severity"], c["type"] = s["severity"], s["type"]
        c["confidence"] = max(c["confidence"], s["confidence"])

    for c in cards.values():
        n = len(c["evidence"])
        c["priority"] = round(
            SEV_WEIGHT[c["severity"]] * c["confidence"] * (1 + 0.25 * (n - 1)), 2)

    return sorted(cards.values(), key=lambda c: -c["priority"])


if __name__ == "__main__":
    for c in run_pipeline():
        print(f"{c['priority']:>5}  {c['severity']:<6} {c['type']:<10} "
              f"{c['team']:<9} {c['title']}  ({len(c['evidence'])} evidence)")
