"""E-charts"""

import pandas as pd
from models import Settings
from streamlit_echarts import JsCode, st_echarts


def profit_chart(settings: Settings, profit: pd.Series):
    """Renders interactive profit chart"""
    values = profit.cumsum().values
    options = {
        "animationDuration": 1000,
        "title": {"text": "Cummulative profit/loss"},
        "tooltip": {
            "trigger": "item",
            "axisPointer": {"type": "cross", "label": {"backgroundColor": "#6a7985"}},
            "formatter": JsCode(
                f"function (series) {{ return 'Trade ' + series.name + '<br/>' + series.value.toFixed(2) + '{settings.currency_sym}'; }}"
            ).js_code,
        },
        "toolbox": {
            "feature": {
                "dataZoom": {"yAxisIndex": "none"},
                "restore": {},
            }
        },
        "xAxis": {
            # "type": "category",
            "data": profit.index.values.tolist(),
            "name": "Trade #",
            "nameLocation": "middle",
            "nameGap": 30,
        },
        "yAxis": {
            "type": "value",
            "name": "PnL",
            "nameLocation": "middle",
            "nameGap": 50,
        },
        "grid": {"right": 0},
        "series": [{"data": values.tolist(), "type": "line", "areaStyle": {}}],
    }
    st_echarts(options=options, height="500px")
