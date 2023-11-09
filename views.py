"""Streamlit views for the PAI Analyzer app."""

import datetime

import fns
import streamlit as st
from models import DataInput, DataInputType, DateFilter, Settings


def _date_range(
    range_min: datetime.date,
    range_max: datetime.date,
    selected_min: datetime.date = None,
    selected_max: datetime.date = None,
) -> DateFilter:
    value = [
        selected_min if selected_min else range_min,
        selected_max if selected_max else range_max,
    ]
    date_from, date_to = st.slider(
        "Date range",
        range_min,
        range_max,
        value=value,
    )

    return DateFilter(
        date_from=date_from if date_from != range_min else None,
        date_to=date_to if date_to != range_max else None,
    )


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
    comment_filter = None if not comment_filter else comment_filter

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

    data = fns.select_trades(
        data, comment_filter=comment_filter, magic_filter=magic_filter
    )
    closed_trades = data[data["Type"] == "Closed position"]
    date_filter = _date_range(
        closed_trades["Open time"].min().date(),
        closed_trades["Close time"].max().date(),
        used_settings.date_filter.date_from if used_settings.date_filter else None,
        used_settings.date_filter.date_to if used_settings.date_filter else None,
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
