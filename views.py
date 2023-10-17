"""Streamlit views for the PAI Analyzer app."""
import fns
import pandas as pd
import streamlit as st
from models import Settings

query_params = st.experimental_get_query_params()


def _get_param(key, default):
    "Gets a single value of a query parameter or default if not found"
    return query_params.get(key, [default])[0]


def settings():
    """Renders and parsers use settings"""
    data_url = st.text_input(
        "FxBlue URL",
        value=_get_param("data_url", "https://www.fxblue.com/users/alun/csv"),
    )
    comment_filter = st.text_input(
        "Comment filter", value=_get_param("comment_filter", "Perceptrader").strip()
    )
    magic_filter = st.text_input(
        "Magic filter (split with ',' for multiple values)",
        value=_get_param("magic_filter", " ").strip(),
    )
    currency_sym = st.text_input(
        "Deposit currency symbol", value=_get_param("currency_sym", "€")
    )
    override_capital = st.checkbox(
        "Override capital", value=_get_param("override_capital", "true")
    )

    assumed_capital = float(
        st.text_input(
            "Assumed starting capital",
            value=_get_param("assumed_capital", "1000")
            if override_capital
            else str(
                fns.get_deposit(
                    pd.read_csv(data_url, skiprows=1).astype(
                        {
                            "Close time": "datetime64[ns]",
                            "Open time": "datetime64[ns]",
                            "Order comment": "string",
                        }
                    )
                )
            ),
            disabled=not override_capital,
        )
    )
    return Settings(
        data_url=data_url,
        comment_filter=comment_filter,
        magic_filter=magic_filter,
        currency_sym=currency_sym,
        override_capital=override_capital,
        assumed_capital=assumed_capital,
    )
