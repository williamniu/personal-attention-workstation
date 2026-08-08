from __future__ import annotations

import streamlit as st

from hcis.api.app import state_store

st.set_page_config(page_title="HCIS", layout="wide")
st.title("H-1B Career Intelligence System")
st.caption("Local-first · evidence-driven · human-controlled")
st.metric("Desired state", state_store().read()["desired_state"])
st.info("M0 runtime skeleton is active. Data modules are enabled milestone by milestone.")
