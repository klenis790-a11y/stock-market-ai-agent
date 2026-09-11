"""Compact overview of existing session results; no research or price refresh."""
import streamlit as st
from src.ui_contracts import HomePageData
from src.dashboard.components import header
from src.dashboard.portfolio import money, weight
from src.dashboard.history_adapter import load_history, HistoryReadError


def navigate(destination):
    st.session_state['workspace'] = destination


def render():
    header('Home', 'Command center · current session overview')
    research = st.session_state.get('research_result')
    portfolio = st.session_state.get('portfolio_result')
    data = HomePageData(portfolio=portfolio.snapshot if portfolio else None,
                        risk_assessment=portfolio.risk_assessment if portfolio else None,
                        current_analysis=research.analysis if research else None)
    st.subheader('Current portfolio')
    if data.portfolio is None:
        st.info('No portfolio loaded in this session.')
    else:
        snapshot = data.portfolio
        st.caption('PORTFOLIO FACTS / CALCULATED METRICS · As last loaded; no price refresh')
        for col, label, value in zip(st.columns(3), ('Total portfolio value', 'Positions value', 'Cash'),
                                    (snapshot.total_portfolio_value, snapshot.total_positions_value, snapshot.cash)):
            col.metric(label, money(value))
        st.caption(f'Positions: {snapshot.position_count} · Cash weight: {weight(snapshot.cash_weight)} · Largest position: {snapshot.largest_position_ticker or "Unavailable"} · Largest weight: {weight(snapshot.largest_position_weight)}')

    st.subheader('Latest AI research')
    if data.current_analysis is None:
        st.info('No company research has been run in this session.')
        st.caption('Open Research to run a company analysis explicitly.')
    else:
        analysis = data.current_analysis
        st.caption('AI SYNTHESIS · Latest successful session result')
        ticker, recommendation, confidence = st.columns(3)
        ticker.metric('Ticker', analysis.ticker)
        recommendation.metric('Recommendation', analysis.recommendation)
        confidence.metric('Final synthesis confidence', f'{analysis.confidence_score}/100')
        st.write(analysis.reasoning_summary[:400] + ('…' if len(analysis.reasoning_summary) > 400 else ''))
        st.caption('Portfolio context: ' + ('Supplied' if research.portfolio_context_supplied else 'Not supplied')
                   + ' · Historical memory: ' + ('Supplied' if research.memory_context_supplied else 'Not supplied'))
        if research.specialist_results:
            st.caption(f'Multi-agent run: Completed · {len(research.specialist_results)} specialists completed')
        else:
            st.caption('No specialist results captured for this run.')

    st.subheader('Current risk flags')
    st.caption('DETERMINISTIC PORTFOLIO RISK · Configured policy, not AI investment advice')
    if data.risk_assessment is None:
        st.caption('No portfolio risk assessment loaded.')
    else:
        for note in data.risk_assessment.notes:
            st.warning(note)
        if not data.risk_assessment.concentration_policy_evaluable:
            st.caption('Concentration policy is not fully evaluable with the supplied data.')
        elif not data.risk_assessment.notes:
            st.caption('No configured policy limits breached.')

    st.subheader('Recent activity / stored history')
    st.caption('Session status only; no event timestamps or activity log are inferred.')
    if data.current_analysis:
        st.write(f'Latest research completed: {data.current_analysis.ticker}')
    if data.portfolio:
        st.write(f'Portfolio loaded: {data.portfolio.position_count} positions')
    query = st.session_state.get('history_query')
    if not query or not query[0].strip():
        st.info('No decision-history source selected.')
    else:
        st.caption('Explicitly selected history source · Latest stored decision for the selected ticker only')
        try:
            history = load_history(*query)
            if history.decisions:
                item = history.decisions[0]
                st.write(f'{item.ticker} · {item.decision_timestamp} · {item.recommendation} · Confidence: {item.confidence_score}/100')
            else:
                st.info(history.availability['history'].reason)
        except HistoryReadError as error:
            st.info(str(error))

    st.subheader('Quick actions')
    for col, label, destination in zip(st.columns(4),
            ('Research a ticker', 'View Portfolio', 'Inspect Agent Room', 'View Decision History'),
            ('research', 'portfolio', 'agent_room', 'decision_history')):
        col.button(label, on_click=navigate, args=(destination,))
    st.subheader('Performance')
    st.caption('Open Performance to inspect stored outcome summaries. Later observations are required; no results are inferred here.')
