"""Streamlit views for the PAI Analyzer app."""

import fns
import streamlit as st
from models import DataInput, DataInputType, Settings


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
    assumed_capital = float(
        st.text_input(
            "Assumed starting capital",
            value=(
                used_settings.assumed_capital
                if override_capital
                else str(fns.get_deposit(fns.get_data(data_input)))
            ),
            disabled=not override_capital,
        )
    )
    return Settings(
        data_input=data_input,
        comment_filter=comment_filter,
        magic_filter=magic_filter,
        currency_sym=currency_sym,
        override_capital=override_capital,
        assumed_capital=assumed_capital,
    )
