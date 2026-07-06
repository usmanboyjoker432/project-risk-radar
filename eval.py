"""Score the pipeline against planted.json ground truth. Run: python3 eval.py"""

import json
from pipeline import run_pipeline

# planted standup signals are identified by a phrase in their evidence
STANDUP_PHRASES = {
    "standup-ravi-auth": "waiting on the auth team",
    "standup-lena-slip": "might slip",
    "standup-jen-legal": "sign-off from legal",
}

with open("planted.json") as f:
    planted = json.load(f)

cards = run_pipeline()
card_keys = {c["key"] for c in cards}
all_evidence = " | ".join(e for c in cards for e in c["evidence"]).lower()

hits, misses = [], []
for p in planted:
    if p["id"].startswith("standup-"):
        found = STANDUP_PHRASES[p["id"]].lower() in all_evidence
    else:
        found = p["id"] in card_keys
    (hits if found else misses).append(p)

planted_ticket_ids = {p["id"] for p in planted}
false_pos = [c for c in cards
             if c["key"] not in planted_ticket_ids
             and not c["key"].startswith("standup:")]
# standup cards count as FP only if they match no planted phrase
for c in cards:
    if c["key"].startswith("standup:"):
        ev = " ".join(c["evidence"]).lower()
        if not any(ph in ev for ph in STANDUP_PHRASES.values()):
            false_pos.append(c)

recall = len(hits) / len(planted)
precision = (len(cards) - len(false_pos)) / len(cards) if cards else 0

print(f"Planted signals: {len(planted)}   Cards produced: {len(cards)}")
print(f"Recall:    {recall:.2f}  ({len(hits)}/{len(planted)} planted signals caught)")
print(f"Precision: {precision:.2f}  ({len(false_pos)} false-positive cards)")
if misses:
    print("\nMissed:")
    for p in misses:
        print(f"  - {p['id']}: {p['note']}")
