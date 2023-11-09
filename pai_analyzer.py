"""
Streamlit app for Perceptrader monitoring and analysis
"""

import charts
import fns
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import views

# Test URLs
# http://localhost:8501?data_input_type=MT5%20tester%20XLSX&data_url=https%3A//docs.google.com/spreadsheets/d/1xyagwvas0dh7gOzABCZ6bGzElP-zboZ2/edit%3Fusp%3Dsharing%26ouid%3D108957322456978477968%26rtpof%3Dtrue%26sd%3Dtrue&comment_filter=%20&magic_filter=%20&currency_sym=%E2%82%AC&assumed_capital=10000.0&override_capital=False
# http://localhost:8501?data_input_type=MT5%20tester%20XLSX&data_url=https%3A//docs.google.com/spreadsheets/d/1lMyYAGhBRASp0GcoeytLBpOPGwNvzB3I/edit%3Fusp%3Dsharing%26ouid%3D108957322456978477968%26rtpof%3Dtrue%26sd%3Dtrue&comment_filter=Perceptrader&magic_filter=%20&currency_sym=%24&assumed_capital=10000.0&override_capital=False

st.title("Perceptrader analyzer")


settings = views.settings()


st.subheader("Permalink")
st.write(
    "Use the copy button in the window below to copy the permalink to your settings"
)
st.code(fns.permalink(settings))

# prepare data
data = fns.get_data(settings.data_input)


assumed_capital = (
    settings.assumed_capital if settings.override_capital else fns.get_deposit(data)
)


trades = fns.select_trades(
    data, comment_filter=settings.comment_filter, magic_filter=settings.magic_filter
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
    "Magic number",
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

closed_trades = fns.select_trades(closed_trades, date_filter=settings.date_filter)

st.header("Open trades")
st.write(open_trades[::-1])


st.header("Charts")
symbol = st.selectbox(
    "Symbol",
    [
        sym[0 : min(6, len(sym))]
        for sym in trades.Symbol.unique()
        if isinstance(sym, str)
    ],
)

st.components.v1.html(
    f"""<!-- TradingView Widget BEGIN -->
<div class="tradingview-widget-container">
  <div id="tradingview_6461e"></div>
  <div class="tradingview-widget-copyright"><a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank"><span class="blue-text">Track all markets on TradingView</span></a></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget(
  {{
  "width": "auto",
  "height": 500,
  "symbol": "OANDA:{symbol}",
  "interval": "1H",
  "timezone": "Etc/UTC",
  "theme": "light",
  "style": "1",
  "locale": "en",
  "enable_publishing": false,
  "backgroundColor": "rgba(255, 255, 255, 1)",
  "hide_top_toolbar": false,
  "hide_legend": true,
  "hide_volume": true,
  "container_id": "tradingview_6461e"
}}
  );
  </script>
</div>
<!-- TradingView Widget END -->""",
    height=500,
)


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
t_row("Total trading days", days_total)
t_row("Total trades", len(closed_trades))
t_row(
    "Closed profit/loss",
    f"{closed_profit:.2f}{settings.currency_sym} ({closed_profit_pct:.2f}%)",
)
t_row("Traded lots", f"{lots:.2f}")
t_row(
    "Profit/loss per 0.01 lot",
    f"{closed_profit / (lots / 0.01):.2f}{settings.currency_sym}",
)
t_row("Profit factor", f"{won_profit / lost_loss:.2f}")
t_row(
    "Open profit/loss",
    f"{open_profit:.2f}{settings.currency_sym} ({open_profit_pct:.2f}%)",
)
t_row("Approximate gain", f"{closed_profit / settings.assumed_capital * 100:.2f}%")
t_row("Annualized gain", f"{annual * 100:.2f}%")

# closed_trades["Net profit"].cumsum().plot()
# plt.title("Closed profit/loss")
# plt.xlabel("Trade #")
# plt.ylabel(f"Cumulative profit, {settings.currency_sym}")
# plt.grid(linestyle="dotted")
# st.pyplot(plt)

charts.profit_chart(settings, closed_trades["Net profit"])

st.header("Cost of trading")

swaps = closed_trades["Swap"].sum()
comissions = closed_trades["Commission"].sum()
fees = swaps + comissions
closed_profit_gross = closed_trades["Profit"].sum()
fees_pct = -100 * fees / closed_profit_gross

t_row("Fees", f"{-fees:.2f}{settings.currency_sym}")
t_row(
    "Swaps/Commisions",
    f"{-swaps:.2f}{settings.currency_sym}/{-comissions:.2f}{settings.currency_sym}",
)
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
    "This section shows statistics on trades grouped by the same PAI grid. `GridTrades=0` means only initial trade was taken, no grid."
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
                GridTrades=df["Net profit"].count() - 1,
                Lots=df["Lots"].sum(),
                NetProfit=df["Net profit"].sum(),
                PerLot=df["Net profit"].sum() / (100 * df["Lots"].sum()),
                Fees=(df["Commission"] + df["Swap"]).sum(),
                Direction=df["Buy/sell"].unique(),
            ),
            index=[0],
        ).set_index(["Direction"])
    )
    .astype({"GridTrades": "int32"})[::-1]
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
            (
                key,
                st.column_config.NumberColumn(
                    key, format="%.2f" + settings.currency_sym
                ),
            )
            for key in ["NetProfit", "PerLot", "Fees"]
        ]
    ),
)

plt.figure()
grid_trades.groupby("GridTrades").size().plot(kind="bar", rot=0)
plt.title("Grid level frequency")
plt.xlabel("Total grid trades\n(0 = only initial trade)")
plt.ylabel("Count")
plt.grid(linestyle="dotted")
st.pyplot(plt)

st.subheader("Grid gaps (aka trade distance)")

st.write(
    """
    This shows the grid gaps between trades in pips for trades with at least one grid trade. Grid trades with only intial trade (no grid trades) are skipped. When using the smart grid (`Smart Distance = True`), the gaps should be not equal and depend on volatility.
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
