"""
Streamlit app for Perceptrader monitoring and analysis
"""

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

st.title("Perceptrader analyzer")

data_url = st.text_input("FxBlue URL", value="https://www.fxblue.com/users/alun/csv")
comment_filter = st.text_input("Comment filter", value="Perceptrader")
currency_sym = st.text_input("Deposit currency symbol", value="€")
assumed_capital = float(st.text_input("Assumed starting capital", value="1000"))

data = pd.read_csv(data_url, skiprows=1)
pai_trades = data[
    data["Order comment"].str.contains(comment_filter).fillna(False)
].astype({"Close time": "datetime64[ns]", "Open time": "datetime64[ns]"})

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


open_trades_mask = pai_trades["Type"] == "Open position"
closed_trades_mask = pai_trades["Type"] == "Closed position"

open_trades = pai_trades[open_trades_mask][
    [col for col in columns if col not in skip_columns_open]
].reset_index(drop=True)
closed_trades = pai_trades[closed_trades_mask][columns].reset_index(drop=True)

st.header("Open trades")
st.write(open_trades[::-1])

st.header("Closed trades")
st.write(closed_trades[::-1])

st.header("Profitability")

closed_profit = closed_trades["Net profit"].sum()
closed_profit_pct = 100 * closed_profit / assumed_capital
open_profit = open_trades["Net profit"].sum()
open_profit_pct = 100 * open_profit / (assumed_capital + closed_profit)
first_ts = closed_trades["Open time"].min()
last_ts = closed_trades["Close time"].max()
days_total = (last_ts - first_ts).days

col1, col2 = st.columns([1, 3], gap="small")

col1.write("Began trading")
col2.write(str(first_ts))
col1.write("Last closed trade")
col2.write(str(last_ts))
col1.write("Total days running")
col2.write(str(days_total))
col1.write("Closed profit/loss")
col2.write(f"{closed_profit:.2f}{currency_sym} ({closed_profit_pct:.2f}%)")
col1.write("Open profit/loss")
col2.write(f"{open_profit:.2f}{currency_sym} ({open_profit_pct:.2f}%)")


closed_trades["Net profit"].cumsum().plot()
plt.title("Closed profit/loss")
plt.xlabel("Trade #")
plt.ylabel(f"Cumulative profit, {currency_sym}")
plt.grid(linestyle="dotted")
st.pyplot(plt)

st.header("Cost of trading")

col1, col2, _ = st.columns([1, 1, 2], gap="small")

fees = closed_trades["Swap"].sum() + closed_trades["Commission"].sum()
col1.write("Fees")
col2.write(str(fees) + currency_sym)

closed_profit_gross = closed_trades["Profit"].sum()
col1, col2, col3 = st.columns([1, 1, 2], gap="small")
col1.write("% of profit")
col2.write(f"{-100 * fees/ closed_profit_gross:.2f}%")
col3.write("<- % of gross profit shared with the broker")
