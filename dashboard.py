"""Launch with .venv/bin/python -m streamlit run dashboard.py."""
import streamlit as st
from src.configuration import load_local_environment
from src.ui_contracts import DASHBOARD_PAGES
from src.dashboard import home, research, portfolio, agent_room, decision_history, performance, technical_research

RENDERERS = {
    'home': home.render, 'research': research.render, 'portfolio': portfolio.render,
    'agent_room': agent_room.render, 'decision_history': decision_history.render,
    'performance': performance.render, 'technical_research': technical_research.render,
}

st.set_page_config(page_title='Investment Research', layout='wide')
try:
    load_local_environment()
except RuntimeError:
    st.error('Local environment configuration could not be loaded. Check server configuration.')
    st.stop()
st.sidebar.title('Investment Research')
st.sidebar.caption('V0.5 · Investment research')
page = st.sidebar.radio('Workspace', [p.key for p in DASHBOARD_PAGES], key='workspace',
                        format_func=lambda key: 'Home' if key == 'home' else next(p.title for p in DASHBOARD_PAGES if p.key == key))
st.sidebar.caption('Research runs only on explicit submission. History reads use selected sources. Saving is explicit.')
RENDERERS[page]()
