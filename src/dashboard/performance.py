"""Read-only descriptive evaluation of stored outcomes, never simulated trading."""
import streamlit as st
from src.dashboard.components import header
from src.dashboard.performance_adapter import load_performance
from src.dashboard.history_adapter import HistoryReadError


def percent(value):
    return 'Unavailable' if value is None else f'{value:.2%}'


def render():
    header('Performance', 'Observed outcomes from preserved decisions · descriptive, not strategy evaluation')
    query = st.session_state.get('performance_query', st.session_state.get('history_query', ('', '')))
    with st.form('performance_source'):
        path = st.text_input('Decision database path', value=query[0])
        ticker = st.text_input('Stored ticker', value=query[1])
        submitted = st.form_submit_button('Load Performance')
    if submitted:
        query = (path, ticker)
        st.session_state['performance_query'] = query
    from src.dashboard.evaluation import performance_section
    performance_section(*query)
    st.subheader('Legacy outcomes · V0.3 / V0.5')
    try:
        data = load_performance(*query)
    except HistoryReadError as error:
        st.error(str(error))
        return
    if not data.availability.data_available:
        st.info(data.availability.reason)
        st.caption('Saved decisions require later outcome observations before performance can be measured.')
        return
    st.caption('Selected ticker only. Each decision/horizon outcome is one observation; repeated horizons for a decision are not independent samples.')
    stock_count = data.summary['stock_return_count']
    st.metric('Evaluated outcomes with stock returns', stock_count)
    st.caption(f'Unique decisions represented: {len({row["decision_id"] for row in data.rows})}')
    st.warning('These descriptive statistics should not be treated as evidence of a robust edge or statistical significance, especially with limited samples.')
    st.caption('Underlying stock returns are not trading returns or recommendation correctness. Trim/Avoid do not imply short positions. No annualization or confidence calibration is performed.')
    st.caption('Pooled averages may mix horizons and benchmarks; benchmark/excess samples can differ from stock samples. Inspect the stored table and horizon breakdown before comparing averages.')
    for column, key in zip(st.columns(3), ('stock_return', 'benchmark_return', 'excess_return')):
        column.metric('Average ' + key.replace('_', ' '), percent(data.summary['average_' + key]))
        column.caption(f'n = {data.summary[key + "_count"]}')
    for label, key in (('Positive stock return', 'positive_return'), ('Benchmark outperformance', 'benchmark_outperformance')):
        st.write(f'{label}: {percent(data.summary[key + "_rate"])} · count: {data.summary[key + "_count"] if data.summary[key + "_count"] is not None else "Unavailable"}')
    st.subheader('Stored evaluated outcomes')
    st.caption('Returns below are stored decimal values. Missing values are unavailable, never zero.')
    st.dataframe(data.rows, hide_index=True)
    for title, groups in (('Original recommendation breakdown', data.recommendations),
                          ('Stored horizon breakdown', data.horizons),
                          ('Observed outcome summary by confidence', data.confidence_groups)):
        st.subheader(title)
        st.dataframe([{'Group': key, **values} for key, values in groups.items()], hide_index=True)
    st.caption('Confidence buckets use [0,50), [50,60), [60,70), [70,80), [80,90), [90,100]. No calibration claim is implied.')
    # Display threshold only, not a claim of statistical sufficiency.
    if stock_count >= 5 and len(data.recommendations) >= 2:
        st.subheader('Outcome counts by original recommendation')
        st.bar_chart([{'Recommendation': key, 'Evaluated outcomes': values['stock_return_count']}
                      for key, values in data.recommendations.items()], x='Recommendation', y='Evaluated outcomes')
