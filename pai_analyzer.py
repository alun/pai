"""
Streamlit app for Perceptrader monitoring and analysis
"""

from urllib.parse import quote, urlparse, urlunparse

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

st.title("Perceptrader analyzer")

query_params = st.experimental_get_query_params()


def get_param(key, default):
    "Gets a single value of a query parameter or default if not found"
    return query_params.get(key, [default])[0]


data_url = st.text_input(
    "FxBlue URL", value=get_param("data_url", "https://www.fxblue.com/users/alun/csv")
)
comment_filter = st.text_input(
    "Comment filter", value=get_param("comment_filter", "Perceptrader").strip()
)
currency_sym = st.text_input(
    "Deposit currency symbol", value=get_param("currency_sym", "€")
)
assumed_capital = st.text_input(
    "Assumed starting capital", value=get_param("assumed_capital", "1000")
)

urlparts = urlparse("https://pai-monitor.streamlit.app/")

urlparts = urlparts._replace(
    query="&".join(
        [
            "data_url=" + quote(data_url),
            "comment_filter=" + quote(comment_filter if comment_filter else " "),
            "currency_sym=" + quote(currency_sym),
            "assumed_capital=" + quote(assumed_capital),
        ]
    )
)
permalink = urlunparse(urlparts)
st.subheader("Permalink")
st.write(
    "Use the copy button in the window below to copy the permalink to your settings"
)
st.code(permalink)

assumed_capital = float(assumed_capital)

data = pd.read_csv(data_url, skiprows=1).astype(
    {
        "Close time": "datetime64[ns]",
        "Open time": "datetime64[ns]",
        "Order comment": "string",
    }
)

filter_mask = (
    data["Order comment"].str.contains(comment_filter).fillna(not comment_filter)
)
trades = data[filter_mask]

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

existing_columns = [col for col in trades.columns if col in columns]

open_trades = trades[open_trades_mask][
    [col for col in existing_columns if col not in skip_columns_open]
].reset_index(drop=True)
closed_trades = trades[closed_trades_mask][existing_columns].reset_index(drop=True)

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
    col2.text(str(value))
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

swaps = closed_trades["Swap"].sum()
comissions = closed_trades["Commission"].sum()
fees = swaps + comissions
closed_profit_gross = closed_trades["Profit"].sum()
fees_pct = -100 * fees / closed_profit_gross

t_row("Fees", f"{-fees:.2f}{currency_sym}")
t_row("Swaps/Commisions", f"{-swaps:.2f}{currency_sym}/{-comissions:.2f}{currency_sym}")
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
    "This section shows statistics on trades grouped by the same PAI grid. `Trades=0` means only initial trade was taken, no grid."
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
                Trades=df["Net profit"].count() - 1,
                Lots=df["Lots"].sum(),
                NetProfit=df["Net profit"].sum(),
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

st.dataframe(
    grid_trades,
    use_container_width=True,
    column_config=dict(
        [
            (key, st.column_config.NumberColumn(key, format="%.2f" + currency_sym))
            for key in ["NetProfit", "PerLot", "Fees"]
        ]
    ),
)

plt.figure()
grid_trades.groupby("Trades").size().plot(kind="bar", rot=0)
plt.title("Grid level frequency")
plt.xlabel("Total grid trades\n(0 = only initial trade)")
plt.ylabel("Count")
st.pyplot(plt)

st.subheader("Grid gaps (aka trade distance)")

st.write(
    """
    This shows the grid gaps between trades in pips for trades with at least one grid trade. Trades with only intial trade are skipped. When using the smart grid (`Smart Distance = True`), the gaps should be not equal and depend on volatility.
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

st.dataframe(
    grid_gaps[~grid_gaps.apply(pd.isna).all("columns")][::-1],
    use_container_width=True,
)
