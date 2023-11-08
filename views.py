"""Streamlit views for the PAI Analyzer app."""

from datetime import datetime

import fns
import streamlit as st
from models import DataInput, DataInputType, DateFilter, Settings


def _date_filter(min_time: datetime, max_time: datetime) -> DateFilter:
    filter_close_time_from = st.checkbox("Start date filter", value=False)
    close_time_from = None
    if filter_close_time_from:
        close_time_from = st.date_input(
            "Start date",
            value=min_time,
            min_value=min_time,
            max_value=max_time,
        )

    filter_close_time_to = st.checkbox("End date filter", value=False)
    close_time_to = None
    if filter_close_time_to:
        close_time_to = st.date_input(
            "End date", min_value=close_time_from, max_value=max_time
        )

    return DateFilter(close_time_from=close_time_from, close_time_to=close_time_to)


def settings() -> Settings:
    """Renders UI for user settings"""

    used_settings = fns.read_url_settings()
    input_types_options = fns.values(DataInputType)
    data_input = DataInput(
        input_type=DataInputType(
            st.selectbox(
                "Input URL type",
                options=input_types_options,
                index=input_types_options.index(used_settings.data_input.input_type),
            )
        ),
        data_url=st.text_input("Input URL", value=used_settings.data_input.data_url),
    )
    comment_filter = st.text_input("Comment filter", value=used_settings.comment_filter)
    magic_filter = st.text_input(
        "Magic filter (split with ',' for multiple values)",
        value=used_settings.magic_filter,
    )
    currency_sym = st.text_input(
        "Deposit currency symbol", value=used_settings.currency_sym
    )
    override_capital = st.checkbox(
        "Override capital", value=used_settings.override_capital
    )
    data = fns.get_data(data_input)
    assumed_capital = float(
        st.text_input(
            "Assumed starting capital",
            value=(
                used_settings.assumed_capital
                if override_capital
                else str(fns.get_deposit(data))
            ),
            disabled=not override_capital,
        )
    )

    closed_trades = data[data["Type"] == "Closed position"]
    date_filter = _date_filter(
        closed_trades["Close time"].min(),
        closed_trades["Close time"].max(),
    )

    return Settings(
        data_input=data_input,
        comment_filter=comment_filter,
        magic_filter=magic_filter,
        currency_sym=currency_sym,
        override_capital=override_capital,
        assumed_capital=assumed_capital,
        date_filter=date_filter,
    )
