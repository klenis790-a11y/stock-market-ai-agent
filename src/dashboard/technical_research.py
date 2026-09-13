"""Technical page: presentation over explicit adapter actions, no financial formulas."""
import streamlit as st
from src.dashboard import technical_adapter as adapter


def show_interpretation(signal, packet):
    p=signal['provenance'];a=signal['analysis']
    st.subheader(f"{p['symbol']} · {a['signal']}")
    st.caption('AI INTERPRETATION · Technical research signal — not a trade instruction.')
    st.write(f"Confidence: {a['confidence']}/100 · {adapter.HORIZON_LABELS.get(signal['horizon'],signal['horizon'])}")
    st.caption(f"Market as-of: {p['requested_as_of']} · Latest completed session: {p['latest_completed_session']}")
    st.caption('Confidence is evidence strength, not probability of success.')
    for name in ('summary','thesis'):
        st.markdown('**'+name.title()+'**')
        st.write(a[name]['text'])
        st.table(adapter.evidence_rows(packet,a[name]['evidence_ids']))
    with st.expander('Supporting and conflicting evidence'):
        for key,label in (('supporting_evidence_ids','Supporting'),('conflicting_evidence_ids','Conflicting')):
            st.markdown('**'+label+'**')
            if a[key]:st.table(adapter.evidence_rows(packet,a[key]))
            else:st.caption('No cited entries.')
    for key,label in (('confirmation_conditions','Confirmation conditions · FORECAST'),
                      ('invalidation_conditions','Invalidation conditions · FORECAST'),('risk_notes','Risk notes')):
        with st.expander(label):
            for statement in a[key]:
                st.write(statement['text'])
                st.table(adapter.evidence_rows(packet,statement['evidence_ids']))
            if not a[key]:st.caption('No preserved entries.')
    with st.expander('Missing-data notes'):
        st.write(a['missing_data_acknowledgement'] or 'No missing-data acknowledgement recorded.')
        if a['missing_evidence_ids']:st.table(adapter.evidence_rows(packet,a['missing_evidence_ids']))
    with st.expander('Technical snapshot · retrieved facts and calculated metrics'):
        st.caption('RAW daily OHLCV · completed sessions only. Returns retain their labeled percent or decimal units.')
        st.table(adapter.evidence_rows(packet))
    with st.expander('Evidence catalog and methodology'):
        st.table(adapter.evidence_rows(packet))
        st.write(packet['provenance'])
        st.caption(f"Evidence: {signal['evidence_catalog_version']} · Analyst: {signal['analyst_methodology_version']} · Model: {signal['model']}")


def evaluation_controls(path, record, verified, as_of):
    st.subheader('Technical evaluation · explicit actions')
    view=adapter.evaluation_view(path,record,as_of,market_verified=verified)
    if view['reason']:st.info(view['reason'])
    if view['can_enroll'] and st.button('Enroll for Evaluation',key='tech_enroll_'+record.record_id):
        adapter.enroll(path,record.record_id,adapter.now(),market_verified=verified)
        st.success('Evaluation enrollment saved.')
        view=adapter.evaluation_view(path,record,adapter.now(),market_verified=verified)
    item=view['enrollment']
    if item is None:return
    st.write(f'Research horizon: {adapter.HORIZON_LABELS[item.analysis_horizon]} · Evaluation checkpoint: {item.horizon.length} completed sessions after the reference session')
    st.write('Eligibility: '+view['target'].eligibility)
    for label,session in (('Reference',view['target'].reference),('Target',view['target'].target)):
        if session:st.caption(f'{label} session: {session.date} · close {session.closes_at.isoformat()}')
    with st.expander('Evaluation policy'):
        st.write(f'Benchmark: {item.methodology.benchmark_symbol}')
        st.caption(item.methodology.benchmark_policy_version)
        st.caption(item.methodology.price_policy_version)
        st.caption(f'{item.methodology.version} · {item.horizon_mapping_version} · {item.reference_policy_version}')
        st.caption('RAW technical inputs and provider-adjusted evaluation closes have separate semantics. Record creation anchors evaluation; generation time is not inferred.')
    if view['can_collect'] and st.button('Collect Evaluation Observation',key='tech_collect_'+item.enrollment_id):
        adapter.collect(path,item.enrollment_id,adapter.now(),market_verified=verified)
        st.success('Observation pair saved.')
        view=adapter.evaluation_view(path,record,adapter.now(),market_verified=verified)
    if view['observations']:
        st.write('Evaluation completeness: '+view['result'].evaluation.completeness)
        st.table(adapter.result_rows(view['result']))
        with st.expander('Factual evaluation observations'):
            for observation in view['observations']:
                st.caption(f'RETRIEVED FACT · {observation.point} · {observation.effective_at}')
                for name in ('stock','benchmark'):
                    price=getattr(observation,name)
                    st.write(f'{name}: '+('Unavailable' if price is None else f'{price.symbol} · adjusted close {price.price} · retrieved {price.retrieved_at}'))
    else:st.info('No stored observations yet. Collection is available only after the target session completes.')


def show_summary(metrics):
    st.subheader('Technical evaluation summary · selected ticker')
    st.caption(f"Enrolled: {metrics['total_enrolled']} · Evaluated: {metrics['evaluated_count']} · Benchmark pairs: {metrics['benchmark_count']}")
    if not metrics['evaluated_count']:
        st.info('No evaluated technical signal outcomes are available yet.')
        return
    st.info('Results are descriptive and based on a limited sample. '+metrics['sample_warning'])
    st.caption(' · '.join(f"{name}: {values['evaluated_count']} evaluated" for name,values in metrics['by_signal'].items()))
    if metrics['pooled_horizons']:st.warning('Pooled checkpoint lengths differ; inspect the horizon breakdown.')
    keys=('average_stock_return','median_stock_return','average_excess_return','directional_count',
          'directional_success_count','directional_success_rate','benchmark_count',
          'benchmark_outperformance_count','benchmark_outperformance_rate')
    st.caption('Provider-adjusted returns. Directional denominator excludes NEUTRAL; benchmark denominator includes only stock/benchmark pairs.')
    st.table([{'Metric':key.replace('_',' '),'Value':('Unavailable' if metrics[key] is None else
        f'{metrics[key]:.2%}' if 'return' in key or key.endswith('_rate') else str(metrics[key]))} for key in keys])
    with st.expander('Breakdown by analysis horizon'):
        for name,values in metrics['by_analysis_horizon'].items():
            st.write(adapter.HORIZON_LABELS[name]);st.write(values)


def render():
    st.caption('V0.7 · TECHNICAL RESEARCH')
    st.title('Technical Research')
    st.write('Completed daily price/volume evidence and short-term research, separate from fundamental analysis.')
    verified=st.checkbox('Confirm the selected research/history ticker and VOO are US-listed equities/ETFs compatible with XNYS',key='tech_market')
    with st.form('tech_run_form'):
        ticker=st.text_input('Ticker',placeholder='AAPL',key='tech_ticker')
        horizon=st.selectbox('Technical research horizon',adapter.HORIZONS,format_func=adapter.HORIZON_LABELS.get,key='tech_horizon')
        run=st.form_submit_button('Run Technical Research')
    if run:
        for key in ('tech_run','tech_prepared','tech_saved','tech_error'):
            st.session_state.pop(key,None)
        try:
            with st.spinner('Retrieving completed daily bars and analyzing technical evidence…'):
                st.session_state['tech_run']=adapter.run_technical_research(ticker,horizon,adapter.now(),market_verified=verified)
        except adapter.TechnicalActionError as error:st.session_state['tech_error']=str(error)
    if st.session_state.get('tech_error'):st.error(st.session_state['tech_error'])
    bundle=st.session_state.get('tech_run')
    if bundle:
        show_interpretation(adapter.signal_data(bundle),bundle.catalog.to_packet())
    else:st.info('No technical research result loaded. Submit a ticker and approved horizon explicitly.')
    path=st.text_input('Decision database path',value=st.session_state.get('history_query',('', ''))[0],
        placeholder='Explicit local SQLite path',key='tech_db_path',
        help='Save may create this file; history and status reads never create it.')
    if bundle:
        if st.button('Save Technical Signal',key='tech_save'):
            try:
                if 'tech_prepared' not in st.session_state:
                    st.session_state['tech_prepared']=adapter.prepare_save(bundle,adapter.now())
                record=adapter.save_signal(st.session_state['tech_prepared'],path)
                st.session_state['tech_saved']=record
                st.session_state['tech_history_query']=(path,record.symbol)
                st.success('Technical signal saved. Repeated saves reuse this record identity.')
            except adapter.TechnicalActionError as error:st.error(str(error))
        if st.session_state.get('tech_saved'):st.caption('Saved record: '+st.session_state['tech_saved'].record_id)
    st.subheader('Saved technical signal history')
    with st.form('tech_history_form'):
        stored_ticker=st.text_input('Stored ticker',key='tech_stored_ticker',placeholder='AAPL')
        load=st.form_submit_button('Load Technical History')
    if load:st.session_state['tech_history_query']=(path,stored_ticker)
    query=st.session_state.get('tech_history_query')
    if not query:
        st.info('No technical history source loaded. Choose a database path and stored ticker.')
        return
    st.caption(f'Loaded history source: {query[0]} · Stored ticker: {query[1]}')
    try:
        records=adapter.load_history(*query)
        if not records:
            st.info('No saved technical signals for this ticker.');return
        by_id={r.record_id:r for r in records}
        selected=st.selectbox('Saved technical signal',list(by_id),key='tech_selected',
            format_func=lambda key:f'{by_id[key].created_at} · {by_id[key].signal["analysis"]["signal"]} · {key}')
        record=by_id[selected]
        st.caption(f'Preserved historical belief · Record ID: {record.record_id} · Saved: {record.created_at}')
        with st.expander('Preserved signal and evidence'):
            show_interpretation(record.signal,record.evidence_packet)
        evaluation_controls(query[0],record,verified,adapter.now())
        show_summary(adapter.summary(query[0],records))
    except adapter.TechnicalActionError as error:st.error(str(error))
