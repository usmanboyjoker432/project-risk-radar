"""Project Risk Radar — Streamlit dashboard. Run: streamlit run app.py"""

import streamlit as st
from pipeline import run_pipeline

st.set_page_config(page_title="Project Risk Radar", page_icon="🚨", layout="wide")
st.title("🚨 Project Risk Radar")
st.caption("Early signals of risks, dependencies and blockers, mined from "
           "tickets and standup notes. Sorted by priority.")

cards = run_pipeline()

# ---- sidebar filters --------------------------------------------------------
st.sidebar.header("Filters")
all_teams = sorted({c["team"] for c in cards})
f_type = st.sidebar.multiselect("Signal type", ["blocker", "dependency", "risk"],
                                default=["blocker", "dependency", "risk"])
f_sev = st.sidebar.multiselect("Severity", ["high", "medium", "low"],
                               default=["high", "medium", "low"])
f_team = st.sidebar.multiselect("Team", all_teams, default=all_teams)

shown = [c for c in cards
         if c["type"] in f_type and c["severity"] in f_sev and c["team"] in f_team]

# ---- summary row ------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Signals", len(shown))
col2.metric("Blockers", sum(c["type"] == "blocker" for c in shown))
col3.metric("Dependencies", sum(c["type"] == "dependency" for c in shown))
col4.metric("Risks", sum(c["type"] == "risk" for c in shown))
st.divider()

SEV_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}
TYPE_ICON = {"blocker": "⛔", "dependency": "🔗", "risk": "⚠️"}

# ---- signal cards -------------------------------------------------------------
for c in shown:
    header = (f"{SEV_ICON[c['severity']]} {TYPE_ICON[c['type']]} "
              f"[{c['team']}] {c['title']} — priority {c['priority']}")
    with st.expander(header, expanded=c["severity"] == "high"):
        left, right = st.columns([3, 1])
        with left:
            st.markdown("**Evidence:**")
            for e in c["evidence"]:
                st.markdown(f"- {e}")
        with right:
            st.markdown(f"**Type:** {c['type']}")
            st.markdown(f"**Severity:** {c['severity']}")
            st.markdown(f"**Confidence:** {c['confidence']}")
            st.markdown(f"**Owner:** {c['assignee']}")
            b1, b2, b3 = st.columns(3)
            b1.button("✅", key=f"c{c['key']}", help="Confirm")
            b2.button("🚫", key=f"d{c['key']}", help="Dismiss")
            b3.button("💤", key=f"s{c['key']}", help="Snooze")

if not shown:
    st.info("No signals match the current filters.")
