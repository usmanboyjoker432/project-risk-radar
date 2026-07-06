"""Generate synthetic project data: tickets.json, standups.csv, planted.json.

Creates ~50 Jira-style tickets and ~60 standup notes across 3 fictional teams,
with 15 planted problems (blockers, risky slips, dependencies) recorded in
planted.json as evaluation ground truth.
"""

import csv
import json
import random
from datetime import date, timedelta

random.seed(42)

TODAY = date(2026, 7, 6)
TEAMS = {
    "Platform": ["Aisha", "Marco", "Jen"],
    "Payments": ["Ravi", "Sofia", "Tom"],
    "Mobile": ["Lena", "Chris", "Priya"],
}
NORMAL_STANDUPS = [
    "Finished the {t} work, moving on to code review.",
    "Making good progress on {t}, should wrap up tomorrow.",
    "Paired with the team on {t}, tests are passing.",
    "Closed out {t} yesterday, picking up the next item.",
    "No issues, {t} is on track.",
]
TOPICS = ["search indexing", "checkout flow", "push notifications", "billing export",
          "login refactor", "dashboard charts", "rate limiter", "onboarding screens"]

planted = []
tickets = []
tid = 100


def d(days_ago):
    return (TODAY - timedelta(days=days_ago)).isoformat()


def make_ticket(team, title, status, due_in, assignee, **kw):
    global tid
    tid += 1
    t = {
        "id": f"PRJ-{tid}",
        "team": team,
        "title": title,
        "status": status,
        "assignee": assignee,
        "due_date": (TODAY + timedelta(days=due_in)).isoformat(),
        "due_date_history": kw.get("due_date_history", []),
        "status_history": kw.get("status_history", [{"status": status, "date": d(7)}]),
        "last_activity": kw.get("last_activity", d(1)),
        "comments": kw.get("comments", []),
        "blocked_by": kw.get("blocked_by", []),
    }
    tickets.append(t)
    return t


# --- Filler: healthy tickets -------------------------------------------------
for i in range(40):
    team = random.choice(list(TEAMS))
    make_ticket(team, f"{random.choice(TOPICS).title()} task {i+1}",
                random.choice(["In Progress", "To Do", "Done"]),
                due_in=random.randint(2, 14),
                assignee=random.choice(TEAMS[team]))

# --- Planted problems --------------------------------------------------------
# 1-3: tickets stuck in Blocked for days
for team, days, why in [("Platform", 4, "staging environment is down"),
                        ("Payments", 5, "waiting on fraud-check API keys"),
                        ("Mobile", 3, "blocked by app store review")]:
    t = make_ticket(team, f"Integration work ({team})", "Blocked", due_in=3,
                    assignee=TEAMS[team][0],
                    status_history=[{"status": "In Progress", "date": d(10)},
                                    {"status": "Blocked", "date": d(days)}],
                    comments=[{"author": TEAMS[team][1], "date": d(days),
                               "text": f"Blocked: {why}."}])
    planted.append({"id": t["id"], "type": "blocker", "note": why})

# 4-6: due date slipped twice + hedging comment
for team in TEAMS:
    t = make_ticket(team, f"Release prep ({team})", "In Progress", due_in=2,
                    assignee=TEAMS[team][1],
                    due_date_history=[d(20), d(10), (TODAY + timedelta(days=2)).isoformat()],
                    comments=[{"author": TEAMS[team][1], "date": d(2),
                               "text": "Hopefully this lands this week, not sure yet."}])
    planted.append({"id": t["id"], "type": "risk", "note": "due date slipped twice"})

# 7-9: silent tickets - in progress, no activity for a week
for team in TEAMS:
    t = make_ticket(team, f"Data migration ({team})", "In Progress", due_in=4,
                    assignee=TEAMS[team][2], last_activity=d(8))
    planted.append({"id": t["id"], "type": "risk", "note": "no activity 8 days"})

# 10-12: dependency chain A -> B -> C where A is late
chain = []
for i, team in enumerate(TEAMS):
    t = make_ticket(team, f"Auth rollout step {i+1}", "In Progress",
                    due_in=-2 if i == 0 else 5, assignee=TEAMS[team][0],
                    blocked_by=[chain[-1]["id"]] if chain else [],
                    comments=[{"author": TEAMS[team][0], "date": d(1),
                               "text": "This depends on the previous rollout step shipping first."}])
    chain.append(t)
    planted.append({"id": t["id"], "type": "dependency",
                    "note": "chain with late upstream" if i else "upstream item overdue"})

# --- Standups ----------------------------------------------------------------
rows = []
for day in range(10):  # 10 weekdays back
    dt = d(day)
    for team, people in TEAMS.items():
        for p in random.sample(people, 2):
            rows.append([dt, p, team,
                         random.choice(NORMAL_STANDUPS).format(t=random.choice(TOPICS))])

# 13-15: planted standup signals (repeated weak signals)
for day in (1, 2, 3):
    rows.append([d(day), "Ravi", "Payments",
                 "Still waiting on the auth team for the token format, can't move forward."])
planted.append({"id": "standup-ravi-auth", "type": "blocker",
                "note": "repeated 'waiting on auth team' 3 days"})
rows.append([d(2), "Lena", "Mobile",
             "The offline mode work might slip, scope grew after design review."])
planted.append({"id": "standup-lena-slip", "type": "risk", "note": "might slip + scope growth"})
rows.append([d(1), "Jen", "Platform",
             "We need sign-off from legal before enabling data export."])
planted.append({"id": "standup-jen-legal", "type": "dependency", "note": "needs legal sign-off"})

# --- Write files -------------------------------------------------------------
with open("tickets.json", "w") as f:
    json.dump(tickets, f, indent=2)
with open("standups.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "author", "team", "text"])
    w.writerows(rows)
with open("planted.json", "w") as f:
    json.dump(planted, f, indent=2)

print(f"Wrote {len(tickets)} tickets, {len(rows)} standups, {len(planted)} planted signals.")
