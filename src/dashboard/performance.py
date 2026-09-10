"""Reserved performance surface; no calculated analytics."""
import streamlit as st
from src.ui_contracts import PerformancePageData
from src.dashboard.components import header


def render():
    header('Performance', 'Evaluation analytics require legitimate backend support and observed data.')
    data = PerformancePageData()
    st.info(data.availability.reason)
    st.caption('Returns, benchmarks, drawdown and calibration are not calculated here.')
