"""Launch with .venv/bin/python -m streamlit run dashboard.py."""
import streamlit as st
from src.ui_contracts import DASHBOARD_PAGES
from src.dashboard import home, research, portfolio, agent_room, decision_history, performance

RENDERERS = {
    'home': home.render, 'research': research.render, 'portfolio': portfolio.render,
    'agent_room': agent_room.render, 'decision_history': decision_history.render,
    'performance': performance.render,
}

st.set_page_config(page_title='Investment Research', layout='wide')
st.sidebar.title('Investment Research')
st.sidebar.caption('V0.5 · Dashboard shell')
page = st.sidebar.radio('Workspace', [p.key for p in DASHBOARD_PAGES],
                        format_func=lambda key: 'Home' if key == 'home' else next(p.title for p in DASHBOARD_PAGES if p.key == key))
st.sidebar.caption('Research runs only on explicit submission. No automatic history reads or saves.')
RENDERERS[page]()
