"""Small shared shell presentation helpers."""
import streamlit as st
from src.ui_contracts import UISectionAvailability


def header(title, description):
    st.caption('V0.5 · INVESTMENT RESEARCH')
    st.title(title)
    st.write(description)


def sections(data, entries):
    for title, supported, reason in entries:
        state = UISectionAvailability(supported, False, reason)
        data.availability[title] = state
        with st.container(border=True):
            st.subheader(title)
            st.caption('Not loaded' if state.backend_supported else 'Unavailable')
            st.write(state.reason)
