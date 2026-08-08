from __future__ import annotations

import streamlit as st

from hcis.api.app import data_store, state_store
from hcis.domain.runtime import DesiredState

PAGES = (
    "Overview",
    "Candidate Switcher",
    "William Opportunities",
    "Girlfriend Opportunities",
    "Couple Coordination",
    "Companies",
    "Live Jobs",
    "Sponsorship Evidence",
    "Human Verification Queue",
    "Contacts / CRM",
    "Applications",
    "Resume Variants",
    "Browser Tasks",
    "Mail Intake",
    "Reports",
    "Pipeline Health",
    "System Control",
    "Settings",
)

st.set_page_config(page_title="HCIS", layout="wide")
st.title("H-1B Career Intelligence System")
st.caption("Local-first · evidence-driven · human-controlled")
page = st.sidebar.radio("Page", PAGES)

if page == "Overview":
    st.metric("Desired state", state_store().read()["desired_state"])
    st.warning("No live source connection is claimed until its health status is verified.")
elif page == "Sponsorship Evidence":
    st.subheader("Evidence Ledger")
    st.dataframe(data_store().list("evidence"), use_container_width=True)
    st.caption("No-result observations are not negative evidence.")
elif page == "Human Verification Queue":
    st.subheader("Human Reviews")
    st.dataframe(data_store().list("reviews"), use_container_width=True)
    with st.form("review"):
        company_id = st.text_input("Company ID")
        decision = st.selectbox(
            "Decision",
            (
                "CONFIRMED_FIRST_AVAILABLE_LOTTERY",
                "CONFIRMED_FIRST_TIME_H1B",
                "UNKNOWN_NEEDS_VERIFICATION",
                "CONFIRMED_NO_SPONSORSHIP",
            ),
        )
        notes = st.text_area("Notes")
        if st.form_submit_button("Save human review"):
            data_store().append(
                "reviews",
                {
                    "company_id": company_id,
                    "review_type": "SPONSORSHIP",
                    "decision": decision,
                    "reviewer": "user",
                    "notes": notes,
                    "is_current": True,
                },
                "HUMAN_REVIEW_CREATED",
            )
            st.success("Review saved; automatic jobs cannot overwrite it.")
elif page == "System Control":
    st.json(state_store().read())
    left, middle, right = st.columns(3)
    if left.button("Pause"):
        state_store().set(DesiredState.PAUSED)
        st.rerun()
    if middle.button("Resume"):
        state_store().set(DesiredState.SCHEDULED)
        st.rerun()
    if right.button("Stop"):
        state_store().set(DesiredState.STOPPED)
        st.rerun()
elif page == "Pipeline Health":
    st.info("Open Settings/API source-health for configured adapter state and external blockers.")
else:
    collection = {
        "Companies": "companies",
        "Live Jobs": "jobs",
        "Contacts / CRM": "contacts",
        "Applications": "applications",
        "Browser Tasks": "browser-tasks",
        "Mail Intake": "mail-intake",
        "Reports": "reports",
    }.get(page)
    if collection:
        st.dataframe(data_store().list(collection), use_container_width=True)
    else:
        st.info(f"{page} is wired to the shared navigation shell; its workflow arrives in M8–M10.")
