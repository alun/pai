"""Useful functions for PAI Analyzer"""

import datetime
from typing import List
from urllib.parse import quote, urlparse, urlunparse

import numpy as np
import pandas as pd
import streamlit as st
from data.mt5_reader import Mt5Reader
from models import DataInput, DataInputType, DateFilter, Settings
from streamlit_js_eval import get_page_location


def get_data(data_input: DataInput):
    """Reads data from selected input"""
    cannonical_data = None
    if data_input.input_type == DataInputType.FX_BLUE:
        cannonical_data = pd.read_csv(data_input.data_url, skiprows=1)
    elif data_input.input_type == DataInputType.MT5_TESTER:
        cannonical_data = Mt5Reader(
            data_input.data_url, ignore_cache=False
        ).get_cannoncial_data()
    else:
        raise ValueError("Unsupported data input type: " + data_input.input_type)

    return cannonical_data.astype(
        {
            "Close time": "datetime64[ns]",
            "Open time": "datetime64[ns]",
            "Order comment": "string",
            "Commission": "float64",
            "T/P": "float64",
            "S/L": "float64",
        }
    )


def get_deposit(data: pd.DataFrame):
    """Finds deposit/withdrawal transactions sum"""

    deposit_type_mask = data["Type"] == "Deposit"
    deposit_divident_mask = data["Order comment"].str.contains("dividend") | data[
        "Order comment"
    ].str.contains("adjustment")

    return data[deposit_type_mask & ~deposit_divident_mask]["Profit"].sum()


def values(enum_cls) -> List[str]:
    """Returns all possible enum values"""
    return [const.value for const in enum_cls]


def permalink(settings: Settings) -> str:
    """Returns permalink for the current settings"""
    urlparts = urlparse(get_page_location()["origin"])

    urlparts = urlparts._replace(
        query="&".join(
            [
                "data_input_type=" + quote(settings.data_input.input_type.value),
                "data_url=" + quote(settings.data_input.data_url),
                "comment_filter="
                + quote(settings.comment_filter if settings.comment_filter else " "),
                "magic_filter="
                + quote(settings.magic_filter if settings.magic_filter else " "),
                "currency_sym=" + quote(settings.currency_sym),
                "assumed_capital=" + quote(str(settings.assumed_capital)),
                "override_capital=" + quote(str(settings.override_capital)),
                *(
                    ["date_from=" + quote(str(settings.date_filter.date_from))]
                    if settings.date_filter.date_from is not None
                    else []
                ),
                *(
                    ["date_to=" + quote(str(settings.date_filter.date_to))]
                    if settings.date_filter.date_to is not None
                    else []
                ),
            ]
        )
    )
    return urlunparse(urlparts)


def _get_param(key, default=None):
    """Gets a single value of a query parameter or default if not found"""
    query_params = st.experimental_get_query_params()
    return query_params.get(key, [default])[0]


def _try_parse_date(date_str):
    if date_str is None:
        return None
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def read_url_settings() -> Settings:
    """Reads settings from URL query params with default vlaues"""
    data_input_type = _get_param("data_input_type", DataInputType.FX_BLUE.value)
    if not data_input_type in values(DataInputType):
        data_input_type = DataInputType.FX_BLUE.value

    data_url = _get_param("data_url", "https://www.fxblue.com/users/alun/csv")

    return Settings(
        data_input=DataInput(input_type=data_input_type, data_url=data_url),
        comment_filter=_get_param("comment_filter", "Perceptrader").strip(),
        magic_filter=_get_param("magic_filter", " ").strip(),
        currency_sym=_get_param("currency_sym", "€"),
        override_capital=_get_param("override_capital", "True") == "True",
        assumed_capital=_get_param("assumed_capital", "1000"),
        date_filter=DateFilter(
            date_from=_try_parse_date(_get_param("date_from")),
            date_to=_try_parse_date(_get_param("date_to")),
        ),
    )


def select_trades(
    data,
    comment_filter=None,
    magic_filter=None,
    date_filter=None,
):
    """Selects trades based on filters"""

    comment_mask = (
        data["Order comment"].str.contains(comment_filter).fillna(False)
        if comment_filter
        else True
    )

    magic_mask = (
        data["Magic number"].isin(
            [float(magic.strip()) for magic in magic_filter.split(",")]
        )
        if magic_filter
        else True
    )

    date_from_mask = (
        data["Open time"] >= pd.to_datetime(date_filter.date_from)
        if date_filter is not None and date_filter.date_from is not None
        else True
    )

    date_to_mask = (
        data["Close time"] <= pd.to_datetime(date_filter.date_to)
        if date_filter is not None and date_filter.date_to is not None
        else True
    )

    all_mask = np.repeat(True, len(data))
    return data[all_mask & comment_mask & magic_mask & date_from_mask & date_to_mask]
