"""
Streamlit app for Perceptrader monitoring and analysis
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

st.title("Perceptrader analyzer")

data_url = st.text_input("FxBlue URL", value="https://www.fxblue.com/users/alun/csv")
comment_filter = st.text_input("Comment filter", value="Perceptrader")
currency_sym = st.text_input("Deposit currency symbol", value="€")
assumed_capital = float(st.text_input("Assumed starting capital", value="1000"))

data = pd.read_csv(data_url, skiprows=1)

filter_mask = (
    data["Order comment"].str.contains(comment_filter).fillna(not comment_filter)
)
trades = data[filter_mask].astype(
    {"Close time": "datetime64[ns]", "Open time": "datetime64[ns]"}
)

columns = [
    # "Type",
    # "Ticket",
    "Symbol",
    "Lots",
    "Buy/sell",
    "Open price",
    "Close price",
    "Open time",
    "Close time",
    # "Open date",
    # "Close date",
    "Profit",
    "Swap",
    "Commission",
    "Net profit",
    "T/P",
    "S/L",
    "Pips",
    "Result",
    # "Trade duration (hours)",
    # "Magic number",
    "Order comment",
    # "Account",
    "MAE",
    "MFE",
]
skip_columns_open = [
    "Close time",
    "Close price",
    "Result",
]


open_trades_mask = trades["Type"] == "Open position"
closed_trades_mask = trades["Type"] == "Closed position"

open_trades = trades[open_trades_mask][
    [col for col in columns if col not in skip_columns_open]
].reset_index(drop=True)
closed_trades = trades[closed_trades_mask][columns].reset_index(drop=True)

st.header("Open trades")
st.write(open_trades[::-1])

st.header("Closed trades")
st.write(closed_trades[::-1])

st.header("Statistics")

closed_profit = closed_trades["Net profit"].sum()
closed_profit_pct = 100 * closed_profit / assumed_capital
open_profit = open_trades["Net profit"].sum()
open_profit_pct = 100 * open_profit / (assumed_capital + closed_profit)
first_ts = closed_trades["Open time"].min()
last_ts = closed_trades["Close time"].max()
days_total = (last_ts - first_ts).days

negative_mask = closed_trades["Net profit"] < 0
lost_loss = -closed_trades["Net profit"][negative_mask].sum()
won_profit = closed_trades["Net profit"][~negative_mask].sum()

lots = trades["Lots"].sum()
annual = (1 + closed_profit / assumed_capital) ** (365 / days_total) - 1

st.write("**Net profit/loss is mentioned below, unless otherwise specified**")


def t_row(header, value, comment=None):
    col1, col2, col3 = st.columns([1, 1, 2], gap="small")
    col1.write("**" + header + "**")
    col2.write(str(value))
    if comment:
        col3.write(str(comment))


t_row("Began trading", first_ts)
t_row("Last closed trade", last_ts)
t_row("Total days running", days_total)
t_row("Total trades", len(closed_trades))
t_row(
    "Closed profit/loss",
    f"{closed_profit:.2f}{currency_sym} ({closed_profit_pct:.2f}%)",
)
t_row("Traded lots", f"{lots:.2f}")
t_row("Profit/loss per 0.01 lot", f"{closed_profit / (lots / 0.01):.2f}{currency_sym}")
t_row("Profit factor", f"{won_profit / lost_loss:.2f}")
t_row("Open profit/loss", f"{open_profit:.2f}{currency_sym} ({open_profit_pct:.2f}%)")
t_row("Approximate gain", f"{closed_profit / assumed_capital * 100:.2f}%")
t_row("Annualized gain", f"{annual * 100:.2f}%")

closed_trades["Net profit"].cumsum().plot()
plt.title("Closed profit/loss")
plt.xlabel("Trade #")
plt.ylabel(f"Cumulative profit, {currency_sym}")
plt.grid(linestyle="dotted")
st.pyplot(plt)

st.header("Cost of trading")

col1, col2, _ = st.columns([1, 1, 2], gap="small")

fees = closed_trades["Swap"].sum() + closed_trades["Commission"].sum()
closed_profit_gross = closed_trades["Profit"].sum()
fees_pct = -100 * fees / closed_profit_gross

col1.write("Fees")
col2.write(f"{-fees:.2f}{currency_sym}")

if fees_pct >= 0:
    col1, col2, col3 = st.columns([1, 1, 2], gap="small")

    col1.write("% of profit")
    col2.write(f"{fees_pct:.2f}%")
    col3.write("<- % of gross profit shared with the broker")


st.header("By symbol")

st.dataframe(
    closed_trades.groupby("Symbol")
    .apply(
        lambda df: pd.Series({"Lots": df["Lots"].sum(), "Count": df["Lots"].count()})
    )
    .astype({"Count": "int32"})
)
