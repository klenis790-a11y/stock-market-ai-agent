"""Read-only historical inspection; original decisions and later outcomes stay separate."""
import streamlit as st
from src.dashboard.components import header
from src.dashboard.research import statements
from src.dashboard.history_adapter import load_history, select_decision, HistoryReadError


def display_decision(record, outcomes):
    st.subheader('Original decision')
    st.caption('Historical AI analysis · Preserved decision-time beliefs, not current research')
    st.write(f'Decision made: {record.decision_timestamp}')
    st.write(f'{record.ticker} · Decision ID: {record.decision_id}')
    recommendation, confidence = st.columns(2)
    recommendation.metric('Stored recommendation', record.recommendation)
    confidence.metric('Stored confidence', f'{record.confidence_score}/100')
    st.write('Investment horizon: ' + (record.investment_horizon or 'Not preserved in this historical record'))
    st.write(record.reasoning_summary)
    with st.expander('Preserved assessments'):
        for title, value in [('Fundamental assessment', record.fundamental_assessment),
                             ('Valuation assessment', record.valuation_assessment),
                             ('Earnings assessment', record.earnings_assessment),
                             ('Portfolio assessment · historical AI interpretation', record.portfolio_assessment)]:
            st.markdown(f'**{title}**')
            st.write(value if value is not None else 'Not preserved in this historical record')
    for title, items in [('Bull case', record.bull_case), ('Bear case', record.bear_case),
                         ('Major risks · decision-time vulnerabilities', record.major_risks),
                         ('Thesis invalidation · expectations at decision time', record.thesis_invalidation_conditions),
                         ('Scenarios · forecasts at decision time', record.scenarios),
                         ('Supporting evidence statements', record.supporting_evidence)]:
        with st.expander(title):
            statements(items)
            if not items:
                st.caption('No entries preserved.')
    with st.expander('Missing data recorded at decision time'):
        for item in record.missing_data:
            st.warning(item)
        if not record.missing_data:
            st.caption('No missing-data entries preserved.')
    with st.expander('Historical evidence / context limitations', expanded=True):
        st.info('Reference price, full evidence catalog, original portfolio snapshot and original historical-memory input: Not preserved in this historical record.')
        st.caption('Evidence references below belong to this stored decision. They are not resolved against current Research. Stored material reviews are AI interpretations, not an archived source catalog.')
        for ref, review in record.material_evidence_review.items():
            st.markdown(f'**{ref} · Preserved material evidence review**')
            st.write(review.observation)
            st.write(review.thesis_relevance)
    st.subheader('Later outcomes · separate observations')
    st.caption('These observations are separate from the original decision and do not rewrite its thesis or recommendation. Dates are displayed as stored.')
    linked = [item for item in outcomes if item.decision_id == record.decision_id]
    if not linked:
        st.info('No stored outcomes for this decision.')
    for item in linked:
        with st.expander(f'{item.evaluation_horizon} · Observed: {item.evaluation_timestamp}', expanded=True):
            st.write(f'Evaluation timestamp: {item.evaluation_timestamp}')
            st.table([{'Stored outcome field': name.replace('_', ' '),
                       'Value': 'Unavailable' if getattr(item, name) is None else str(getattr(item, name))}
                      for name in ('evaluation_horizon', 'stock_start_price', 'stock_end_price',
                                   'stock_return', 'benchmark_ticker', 'benchmark_start_price',
                                   'benchmark_end_price', 'benchmark_return', 'excess_return')])
            st.caption('Returns are stored decimal values, not newly calculated performance metrics.')


def render():
    header('Decision History', 'Inspect preserved decisions separately from later observed outcomes.')
    previous_query = st.session_state.get('history_query', ('', ''))
    with st.form('history_input'):
        path = st.text_input('Decision database path', value=previous_query[0], placeholder='Path to an existing SQLite database', key='history_path')
        ticker = st.text_input('Stored ticker', value=previous_query[1], placeholder='AAPL', key='history_ticker')
        st.caption('Ticker-specific history only. No database is created and no current research is retrieved.')
        submitted = st.form_submit_button('Load History')
    if submitted:
        st.session_state['history_query'] = (path, ticker)
        st.session_state.pop('history_selected_id', None)
        st.session_state.pop('history_selection_widget', None)
    query = st.session_state.get('history_query')
    if query is None:
        st.info('No history source loaded. Choose an existing database and ticker.')
        return
    # Only query/selection state is retained; rerenders use read-only store methods.
    try:
        data = load_history(*query)
    except HistoryReadError as error:
        st.error(str(error))
        return
    state = data.availability['history']
    if not state.data_available:
        st.info(state.reason)
        return
    st.caption('Stored decisions · newest timestamp first (existing V0.3 ordering)')
    st.dataframe([{'Decision timestamp': item.decision_timestamp, 'Ticker': item.ticker,
                   'Recommendation': item.recommendation, 'Confidence': item.confidence_score,
                   'Decision ID': item.decision_id} for item in data.decisions], hide_index=True)
    ids = [item.decision_id for item in data.decisions]
    selected = st.session_state.get('history_selected_id')
    if selected is not None and selected not in ids:
        st.info('The previously selected decision is no longer available in this history view.')
        st.session_state.pop('history_selected_id', None)
        st.session_state.pop('history_selection_widget', None)
    # Widget keys are cleaned up on navigation; keep selection as presentation state.
    selected = st.session_state.get('history_selected_id')
    decision_id = st.selectbox('Select stored decision', ids,
                              index=ids.index(selected) if selected in ids else 0,
                              key='history_selection_widget')
    st.session_state['history_selected_id'] = decision_id
    record = select_decision(data, decision_id)
    if record is None:
        st.info('Selected decision is unavailable.')
        return
    display_decision(record, data.outcomes)
    from src.dashboard.evaluation import history_controls
    history_controls(query[0], record)
