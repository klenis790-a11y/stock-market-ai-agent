"""Session-only portfolio inspection backed by existing V0.2 services."""
import streamlit as st
from src.dashboard.components import header
from src.dashboard.portfolio_adapter import load_portfolio, position_rows, PortfolioLoadError


def money(value):
    return 'Unavailable' if value is None else f'{value:,.2f}'


def weight(value):
    return 'Unavailable' if value is None else f'{value:.2%}'


def display_portfolio(data):
    snapshot, risk = data.snapshot, data.risk_assessment
    st.caption('PORTFOLIO FACTS / CALCULATED METRICS · Latest available prices, not real-time')
    for column, label, value in zip(st.columns(3),
                                   ('Total portfolio value', 'Positions value', 'Cash'),
                                   (snapshot.total_portfolio_value, snapshot.total_positions_value, snapshot.cash)):
        column.metric(label, money(value))
    st.caption('Total unrealized gain/loss: unavailable as a backend aggregate; individual values appear below.')
    if not snapshot.positions:
        st.info('No positions supplied. Cash-only portfolio.')
    else:
        st.subheader('Holdings')
        rows = position_rows(data)
        for row in rows:
            for key in ('average_cost', 'current_price', 'cost_basis', 'position_value', 'unrealized_gain_loss'):
                row[key] = money(row[key])
            for key in ('portfolio_weight', 'unrealized_gain_loss_percent'):
                row[key] = weight(row[key])
        st.dataframe(rows, hide_index=True)
    st.subheader('Concentration / risk')
    st.write('Largest position:', snapshot.largest_position_ticker or 'Unavailable / no position')
    st.write('Largest position weight:', weight(snapshot.largest_position_weight))
    st.write('Cash weight:', weight(snapshot.cash_weight))
    st.write('Top-3 weight:', weight(snapshot.top_3_weight))
    st.write('HHI:', snapshot.herfindahl_index if snapshot.herfindahl_index is not None else 'Unavailable')
    st.write('Effective position count:', snapshot.effective_position_count if snapshot.effective_position_count is not None else 'Unavailable')
    if not risk.concentration_policy_evaluable:
        st.warning('Concentration policy cannot be fully evaluated with the available prices/weights.')
    for note in risk.notes:
        st.warning(note)
    if risk.concentration_policy_evaluable and not risk.notes:
        st.caption('No configured policy limits breached.')
    st.caption('Policy flags compare configured limits; they are not investment or trading advice.')


def render():
    header('Portfolio', 'Inspect holdings, latest available valuation and deterministic concentration policy.')
    with st.form('portfolio_input'):
        positions = st.text_area('Positions · TICKER:SHARES:AVERAGE_COST',
                                 help='Separate positions with commas. Leave blank for cash-only.')
        cash = st.number_input('Cash', value=0.0)
        submitted = st.form_submit_button('Load Portfolio', type='primary')
    if submitted:
        st.session_state.pop('portfolio_result', None)
        st.session_state.pop('portfolio_error', None)
        try:
            with st.spinner('Loading latest available portfolio prices…'):
                st.session_state['portfolio_result'] = load_portfolio(positions, cash)
        except PortfolioLoadError as error:
            st.session_state['portfolio_error'] = str(error)
    if st.session_state.get('portfolio_error'):
        st.error(st.session_state['portfolio_error'])
    data = st.session_state.get('portfolio_result')
    if data is None:
        st.info('No portfolio loaded. Loading is explicit and remains in this session only.')
    else:
        display_portfolio(data)
