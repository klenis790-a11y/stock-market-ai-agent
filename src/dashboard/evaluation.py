"""Streamlit presentation; every mutation is guarded by an explicit button."""
from datetime import datetime, timezone
import sqlite3
import streamlit as st
from src.evaluation_models import ACTIVE_HORIZONS
from src.observation_resolution import PRICE_POLICY_VERSION
from src.dashboard import evaluation_adapter as adapter

ERRORS = (ValueError, RuntimeError, OSError, sqlite3.Error, TypeError, KeyError)


def show_views(views):
    if not views:
        st.info('No evaluation enrollments for this selection.')
    for view in views:
        item = view.enrollment
        with st.expander(f'{item.horizon.length} {item.horizon.unit} · {view.target.eligibility}', expanded=True):
            st.write(f'Benchmark: {item.methodology.benchmark_symbol}')
            st.caption(f'Methodology: {item.methodology.version} · Price policy: {item.methodology.price_policy_version}')
            st.caption(f'Reference rule for current collector: {PRICE_POLICY_VERSION}')
            if view.target.reason:
                st.info(view.target.reason)
            for label, session in (('Reference', view.target.reference), ('Target', view.target.target)):
                if session:
                    st.write(f'{label}: {session.date} · close: {session.closes_at.isoformat()}')
            for observation in view.observations:
                st.markdown(f'**RETRIEVED FACT · {observation.point} · {observation.effective_at}**')
                for label, price in (('Stock', observation.stock), ('Benchmark', observation.benchmark)):
                    if price is None:
                        st.write(f'{label}: Unavailable')
                    else:
                        st.write(f'{label}: {price.symbol} · adjusted close {price.price}')
                        st.caption(f'{price.source} · Retrieved {price.retrieved_at} · {price.price_type}')
            if view.result:
                result = view.result
                st.markdown('**CALCULATED METRIC · Provider-adjusted returns**')
                st.write(f'{result.recommendation} · Original confidence {result.confidence_score}/100 · {result.completeness}')
                for label, value in (('Stock', result.stock_return), ('Benchmark', result.benchmark_return), ('Excess', result.excess_return)):
                    st.write(f'{label}: ' + ('Unavailable' if value is None else f'{value:.2%}'))


def history_controls(path, record):
    st.subheader('V0.6 evaluation · explicit actions')
    st.caption('90/365 calendar days from the reference session; non-session targets roll forward. Enrollment never rewrites this decision.')
    st.info('Legacy decisions lack verified analysis-completion metadata. New legacy enrollments remain unresolved; no timestamp is inferred or backfilled.')
    verified = st.checkbox('Confirm this stock and VOO are US-listed equities/ETFs compatible with XNYS', key='evaluation_market')
    horizon = st.selectbox('Evaluation horizon', ACTIVE_HORIZONS,
                           format_func=lambda h: f'{h.length} calendar days')
    try:
        if st.button('Enroll for Evaluation'):
            adapter.enroll_decision(path, record.decision_id, horizon, datetime.now(timezone.utc))
            st.success('Enrollment available. Existing duplicates are reused.')
        views = adapter.decision_evaluations(path, record.decision_id, datetime.now(timezone.utc), market_verified=verified)
        for view in views:
            if view.can_collect and st.button('Collect Observation', key='collect_' + view.enrollment.enrollment_id):
                adapter.collect(path, view.enrollment.enrollment_id, datetime.now(timezone.utc), market_verified=verified)
                st.success('Observation pair saved.')
                views = adapter.decision_evaluations(path, record.decision_id, datetime.now(timezone.utc), market_verified=verified)
                break
        show_views(views)
    except ERRORS:
        st.error('Evaluation action unavailable. Check the selected database, policy and provider configuration. No automatic retry occurs.')


def performance_section(path, ticker):
    st.subheader('V0.6 methodology-controlled evaluations')
    st.caption('Separate from legacy outcomes; cohorts never combine horizons or methodologies. Small samples do not establish an investment edge.')
    if not path or not ticker:
        st.info('No decision-history source selected. Choose an existing database and stored ticker.')
        return
    verified = st.checkbox('Confirm selected ticker and benchmark use the supported US market', key='performance_evaluation_market')
    try:
        views, cohorts = adapter.performance_evaluations(path, ticker, datetime.now(timezone.utc), market_verified=verified)
        st.caption(f'Enrollments: {len(views)} · Stored-result samples: {sum(c[1]["evaluated_count"] for c in cohorts)}')
        show_views(views)
        for item, metrics in cohorts:
            st.write(f'{item.horizon.length} {item.horizon.unit} · {item.methodology.version}')
            st.caption('Provider-adjusted returns. Benchmark rates use paired benchmark_count; positive rates use evaluated_count. Confidence is not a probability.')
            st.table([{'Metric': key, 'Value': 'Unavailable' if value is None else str(value)} for key, value in metrics.items()])
    except ERRORS:
        st.error('Unable to read evaluation data. Check the source and preserved record format.')
