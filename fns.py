"""Useful functions for PAI Analyzer"""

from urllib.parse import quote, urlparse, urlunparse

import pandas as pd
from models import Settings


def get_deposit(data: pd.DataFrame):
    """Finds deposit/withdrawal transactions sum"""
    deposit_type_mask = data["Type"] == "Deposit"
    deposit_divident_mask = data["Order comment"].str.contains("dividend") | data[
        "Order comment"
    ].str.contains("adjustment")

    return data[deposit_type_mask & ~deposit_divident_mask]["Profit"].sum()


def permalink(settings: Settings):
    """Returns permalink for the current settings"""
    urlparts = urlparse("https://pai-monitor.streamlit.app/")
    urlparts = urlparts._replace(
        query="&".join(
            [
                "data_url=" + quote(settings.data_url),
                "comment_filter="
                + quote(settings.comment_filter if settings.comment_filter else " "),
                "magic_filter="
                + quote(settings.magic_filter if settings.magic_filter else " "),
                "currency_sym=" + quote(settings.currency_sym),
                "assumed_capital=" + quote(str(settings.assumed_capital)),
                "override_capital=" + quote(str(settings.override_capital)),
            ]
        )
    )
    return urlunparse(urlparts)
