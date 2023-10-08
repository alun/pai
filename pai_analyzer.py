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

fees = closed_trades["Swap"].sum() + closed_trades["Commission"].sum()
closed_profit_gross = closed_trades["Profit"].sum()
fees_pct = -100 * fees / closed_profit_gross

t_row("Fees", f"{-fees:.2f}{currency_sym}")
if fees_pct >= 0:
    t_row(
        "% of profit",
        f"{fees_pct:.2f}%",
        comment="<- % of gross profit shared with the broker via commissions and swaps",
    )


st.header("By symbol")

st.dataframe(
    closed_trades.groupby("Symbol")
    .apply(
        lambda df: pd.Series({"Lots": df["Lots"].sum(), "Count": df["Lots"].count()})
    )
    .astype({"Count": "int32"})
)

st.header("Grid study")

st.write(
    "This section shows statistics on trades grouped by the same PAI grid. *Trades=1* - only initial trade was taken, no grid."
)

# group by proximity of close time
TRESHOLD = 10 * 10**9  # 10 seconds
time_group = (
    pd.to_datetime(closed_trades["Close time"])
    .sort_index(ascending=True)
    .astype(int)
    .diff()
    .gt(TRESHOLD)
    .cumsum()
)
time_group.name = "Time group"

grid_trades = (
    closed_trades.groupby([time_group, "Symbol"])
    .apply(
        lambda df: pd.DataFrame(
            dict(
                Time=df["Close time"].max(),
                Trades=df["Net profit"].count(),
                NetProfit=df["Net profit"].sum(),
                Lots=df["Lots"].sum(),
                PerLot=df["Net profit"].sum() / (100 * df["Lots"].sum()),
                Fees=(df["Commission"] + df["Swap"]).sum(),
                Direction=df["Buy/sell"].unique(),
            ),
            index=[0],
        ).set_index(["Direction"])
    )
    .astype({"Trades": "int32"})[::-1]
    .reset_index()
    .drop(columns=["Time group"])
    .set_index("Time")
)

t_row("Total grid trades", len(grid_trades))

st.dataframe(grid_trades)

plt.figure()
grid_trades.groupby("Trades").size().plot(kind="bar", rot=0)
plt.title("Grid level frequency")
plt.xlabel("Total grid trades")
plt.ylabel("Count")
st.pyplot(plt)

st.subheader("Grid gaps")

st.write(
    """
    This show the grid gaps between trades in pips for trades with at least one grid trade. Trades with only intial trade are skipped. If usage the smart grid the gaps should be not equal and depend on volatility.
    """
)

close_times = (
    closed_trades.join(time_group)
    .groupby(time_group)
    .apply(lambda df: df["Close time"].max())
    .rename("Time")
)

grid_gaps = (
    closed_trades.groupby([time_group, "Symbol"])
    .apply(
        lambda df: pd.DataFrame(
            df["Open price"].diff().reset_index(drop=True).dropna()
        ).T
    )
    .reset_index(level=2, drop=True)
    .reset_index(level=1)
    .join(close_times)
    .set_index(["Time", "Symbol"])
)

st.dataframe(grid_gaps[~grid_gaps.apply(pd.isna).all("columns")][::-1])
