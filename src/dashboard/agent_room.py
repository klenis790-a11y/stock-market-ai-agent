"""Read-only inspection of the most recent successful same-session research run."""
import streamlit as st
from src.ui_contracts import AgentRoomPageData
from src.dashboard.components import header
from src.dashboard.research import statements


def render():
    header('Agent Room', 'Inspect actual specialist interpretations and final synthesis.')
    run = st.session_state.get('research_result')
    if run is None or run.analysis is None or not run.specialist_results:
        st.info('No multi-agent research run is available in this session.')
        st.write('Run a company analysis from Research first.')
        return

    # References only: no retrieval, execution, inference or session mutation.
    data = AgentRoomPageData(specialist_results=run.specialist_results,
                             synthesis=run.analysis,
                             evidence_package=run.evidence_package,
                             evidence_catalog=run.evidence_catalog)
    analysis = data.synthesis
    st.subheader(analysis.ticker)
    recommendation, confidence = st.columns(2)
    recommendation.metric('Final recommendation', analysis.recommendation)
    confidence.metric('Final synthesis confidence', f'{analysis.confidence_score}/100')
    st.caption('Completed · Most recent successful research run in this session')
    st.caption('Portfolio context: ' + ('Supplied' if run.portfolio_context_supplied else 'Not supplied'))
    st.caption('Historical memory: ' + ('Supplied' if run.memory_context_supplied else 'Not supplied'))

    with st.container(border=True):
        st.subheader('Evidence')
        st.write('Current company evidence supports the interpretations below. Specialist outputs are AI interpretations, not retrieved facts.')
        if data.evidence_catalog is None:
            st.caption('Detailed evidence catalog resolution is unavailable for this captured run. Existing evidence references are shown unchanged.')
        else:
            st.caption('Inspect detailed evidence in Research where supported; this view displays existing references only.')
    st.caption('↓')
    st.subheader('Specialist analysis')
    for item in data.specialist_results:
        with st.container(border=True):
            st.subheader(item.specialist_name)
            st.caption(f'{item.ticker} · Completed')
            st.metric('Specialist confidence', f'{item.confidence_score}/100')
            st.write(item.summary)
            st.caption(f'Missing data: {len(item.missing_data)} entries' if item.missing_data else 'No missing data reported by this specialist.')
            with st.expander(f'Details · {item.specialist_name}'):
                for title, items in [('Key findings', item.key_findings),
                                     ('Risks', item.risks), ('Scenarios', item.scenarios)]:
                    st.markdown(f'**{title}**')
                    statements(items)
                    if not items:
                        st.caption('No entries supplied.')
                st.markdown('**Missing data**')
                for missing in item.missing_data:
                    st.warning(missing)
                if not item.missing_data:
                    st.caption('No missing data reported by this specialist.')

    st.caption('↓')
    with st.container(border=True):
        st.subheader('Portfolio Manager / Final Synthesis')
        st.caption('Portfolio Manager names the synthesis role; it does not imply portfolio context was supplied.')
        st.caption('AI INTERPRETATION · Independent synthesis, not specialist voting or confidence averaging')
        st.write(analysis.reasoning_summary)
        st.caption('↓ Final InvestmentAnalysis')
        recommendation, confidence = st.columns(2)
        recommendation.metric('Recommendation', analysis.recommendation)
        confidence.metric('Final synthesis confidence', f'{analysis.confidence_score}/100')
        for title, items in [('Bull case', analysis.bull_case),
                             ('Bear case', analysis.bear_case),
                             ('Major risks · current vulnerabilities', analysis.major_risks),
                             ('Thesis invalidation · future observations', analysis.thesis_invalidation_conditions)]:
            with st.expander(title):
                statements(items)
                if not items:
                    st.caption('No entries supplied.')
