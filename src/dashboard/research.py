"""Explicit research action and presentation of backend-produced analysis."""
import streamlit as st
from src.models import ForecastStatement
from src.dashboard.components import header
from src.dashboard.decision_save_adapter import save_research_decision, DecisionSaveError
from src.dashboard.research_adapter import run_research, ResearchInputError, ResearchRunError


def statements(items):
    for item in items:
        st.caption('FORECAST' if isinstance(item, ForecastStatement) else 'AI INTERPRETATION')
        st.write(item.text)
        st.caption('Evidence references: ' + ', '.join(item.evidence_refs))


def specialist_results(items):
    """Generic renderer for future same-run capture; never initiates another run."""
    for item in items:
        st.subheader(item.specialist_name)
        st.write(item.summary)
        st.caption(f'Specialist confidence: {item.confidence_score}/100')
        statements(item.key_findings)
        statements(item.risks)
        statements(item.scenarios)
        for missing in item.missing_data:
            st.warning(missing)


def display_result(data):
    analysis = data.analysis
    st.subheader(analysis.ticker)
    recommendation, confidence = st.columns(2)
    recommendation.metric('Recommendation', analysis.recommendation)
    confidence.metric('Final synthesis confidence', f'{analysis.confidence_score}/100')
    st.caption('Standalone company research · AI synthesis · No portfolio context or historical memory')
    for title, text in [('Fundamental assessment', analysis.fundamental_assessment),
                        ('Valuation assessment', analysis.valuation_assessment),
                        ('Earnings assessment', analysis.earnings_assessment),
                        ('Investment thesis / reasoning', analysis.reasoning_summary)]:
        with st.container(border=True):
            st.subheader(title)
            st.caption('AI INTERPRETATION')
            st.write(text)
    bull, bear = st.columns(2)
    with bull:
        st.subheader('Bull case')
        statements(analysis.bull_case)
    with bear:
        st.subheader('Bear case')
        statements(analysis.bear_case)
    with st.expander('Major risks · current vulnerabilities'):
        statements(analysis.major_risks)
    with st.expander('Thesis invalidation · future observations'):
        statements(analysis.thesis_invalidation_conditions)
    with st.expander('Scenarios / forecasts'):
        statements(analysis.scenarios)
    if analysis.missing_data:
        with st.expander('Missing / unavailable data', expanded=True):
            for item in analysis.missing_data:
                st.warning(item)
    with st.expander('Evidence / provenance'):
        st.caption('RETRIEVED FACT / CALCULATED METRIC: backend catalog entries, not AI prose.')
        statements(analysis.supporting_evidence)
        st.info(data.availability['evidence'].reason)
        for ref, review in analysis.material_evidence_review.items():
            st.caption(f'{ref} · AI material-evidence review')
            st.write(review.observation)
            st.write(review.thesis_relevance)
    with st.expander('Specialist analysis'):
        st.caption('Inspect same-run specialist details in Agent Room.' if data.specialist_results else data.availability['specialists'].reason)


def save_controls(data):
    with st.form('save_decision'):
        st.subheader('Save this decision')
        st.caption('Optional local history save for the displayed result. No outcomes or memory are created.')
        path = st.text_input('Decision database path', placeholder='decisions.db', help='Choose a local SQLite file. Save Decision may create it; browsing history never creates it.')
        save = st.form_submit_button('Save Decision')
    if save:
        st.session_state.pop('decision_save_error', None)
        previous = st.session_state.get('saved_decision')
        try:
            record = save_research_decision(data, path,
                decision_id=previous.decision_id if previous else None,
                decision_timestamp=previous.decision_timestamp if previous else None)
            st.session_state['saved_decision'] = record
        except DecisionSaveError as error:
            st.session_state['decision_save_error'] = str(error)
    if st.session_state.get('decision_save_error'):
        st.error(st.session_state['decision_save_error'])
    elif st.session_state.get('saved_decision'):
        record = st.session_state['saved_decision']
        st.success(f'Decision saved. {record.ticker} · {record.decision_timestamp} · {record.decision_id}')


def render():
    header('Research', 'Run standalone multi-agent research and inspect its evidence-grounded synthesis.')
    with st.form('research_input', border=True):
        st.subheader('Run company research')
        ticker_column, action_column = st.columns([4, 1], vertical_alignment='bottom')
        with ticker_column:
            ticker = st.text_input('Ticker', placeholder='AAPL', key='research_ticker')
        with action_column:
            submitted = st.form_submit_button('Run Research', type='primary')
    if submitted:
        st.session_state.pop('research_result', None)
        st.session_state.pop('research_error', None)
        st.session_state.pop('saved_decision', None)
        st.session_state.pop('decision_save_error', None)
        try:
            with st.spinner('Running multi-agent research…'):
                st.session_state['research_result'] = run_research(ticker)
        except (ResearchInputError, ResearchRunError) as error:
            st.session_state['research_error'] = str(error)
    if st.session_state.get('research_error'):
        st.error(st.session_state['research_error'])
    data = st.session_state.get('research_result')
    if data is not None:
        display_result(data)
        save_controls(data)
    else:
        st.info('No research result loaded. Submit a ticker to run research.')
        st.subheader('Evidence / provenance')
        st.caption('Supporting statements and their backend evidence IDs appear after a successful run.')
