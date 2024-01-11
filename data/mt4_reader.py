"""Reader that reads from MT5 strategy tester XLSX report"""

import os
import re
from dataclasses import asdict, dataclass

import pandas as pd
from data.base import (
    FifoPortfolio,
    PosType,
    Trade,
    get_temp_file,
    load_json,
    mkdirs,
    save_json,
)

MT4_TESTER_COL_TYPES = {
    "Time": "datetime64[ns]",
    "Size": "float64",
    "Profit": "float64",
    "Price": "float64",
}


@dataclass
class Mt4Metadata:
    """Metadata about the MT4 report"""

    symbol: str
    deposit: float


SYM_REGEX = re.compile(r"^[^\s]+")


def _get_pos_type(deal: pd.Series) -> PosType:
    """Converts MT4 deal type to PosType"""
    if deal.Type == "buy":
        return PosType.BUY
    if deal.Type == "sell":
        return PosType.SELL
    raise ValueError(f"Invalid deal type: {deal.Type}")


def _read_mt4_metadata(report_headers: pd.DataFrame) -> Mt4Metadata:
    df = report_headers.copy()
    df.columns = [str(col) for col in df.columns]
    df.set_index("0", inplace=True)

    (symbol,) = SYM_REGEX.findall(df.loc["Symbol", "2"])
    return Mt4Metadata(
        symbol=symbol,
        deposit=float(df.loc["Initial deposit", "1"]),
    )


class Mt4HTMLReader:
    """Reader that reads from MT4 strategy tester HTML report"""

    def __init__(
        self, file_url: str, fifo_portfolio: FifoPortfolio, ignore_cache=False
    ):
        self._file_url = file_url
        self._fifo_portfolio = fifo_portfolio
        self._ignore_cache = ignore_cache
        self._comment = None
        self._order_map = {}

        self._load()

    def _load(self):
        """Loads the HTML file from the URL into a dataframe"""

        prefix = self._file_url.replace("/", "_").replace(".html", "")
        cache_file = get_temp_file(Mt4HTMLReader, prefix)
        metadata_cache_file = get_temp_file(Mt4HTMLReader, prefix, "json")

        if (
            not self._ignore_cache
            and os.path.isfile(cache_file)
            and os.path.isfile(metadata_cache_file)
        ):
            print("read from cache " + cache_file)
            self._data = pd.read_csv(cache_file)
            self._data.Time = pd.to_datetime(self._data.Time)
            self._metadata = Mt4Metadata(**load_json(metadata_cache_file))
            self._parse()
            return

        dframes = pd.read_html(self._file_url)
        self._metadata = _read_mt4_metadata(dframes[0])

        df = dframes[-1]
        df.columns = df.iloc[0, :]
        df.drop(0, axis=0, inplace=True)
        df.index = df.iloc[:, 0]
        df = df.iloc[:, 1:]
        # no value in modify positions here
        self._data = df[df.Type != "modify"].reset_index(drop=True)

        self._data = self._data.astype(MT4_TESTER_COL_TYPES)
        self._parse()

        if not self._ignore_cache:
            # cache results
            mkdirs(cache_file)
            self._data.to_csv(cache_file, index=False)
            save_json(metadata_cache_file, asdict(self._metadata))

    def _parse(self):
        """Fills FifoPortfolio"""
        # self._fifo_portfolio.deposit(self._data.iloc[0].Time, self._metadata.deposit)

        for _, row in self._data.iterrows():
            self._process_deal(row)

        if self._fifo_portfolio.has_open_positions():
            raise ValueError("Some positions are still open")

    def _process_deal(self, deal: pd.Series):
        """Process deal record from MT4 stategy tester"""
        if deal.Type in ["buy", "sell"]:
            self._order_map[deal.Order] = deal
            self._fifo_portfolio.open_position(
                Trade(
                    time=deal.Time,
                    symbol=self._metadata.symbol,
                    pos_type=_get_pos_type(deal),
                    volume=deal.Size,
                    price=deal.Price,
                    comment=self._comment,
                    profit=deal.Profit,
                )
            )
        elif deal.Type in ["close", "t/p", "s/l"]:
            open_deal = self._order_map[deal.Order]
            self._fifo_portfolio.close_position(
                Trade(
                    time=deal.Time,
                    symbol=self._metadata.symbol,
                    pos_type=_get_pos_type(open_deal),
                    volume=deal.Size,
                    price=deal.Price,
                    comment=self._comment,
                    profit=deal.Profit,
                )
            )


# TODO add a combined reader that loads a zip file and reads all the reports


if __name__ == "__main__":
    fifo_portfolio = FifoPortfolio()
    fifo_portfolio.deposit(pd.to_datetime("2016-01-01"), 10000)
    INPUT_FILES = [
        "i365/AUDCAD/StrategyTester.htm",
        "i365/NZDCAD/StrategyTester.htm",
        "i365/AUDNZD/StrategyTester.htm",
    ]
    for file in INPUT_FILES:
        Mt4HTMLReader(
            file,
            fifo_portfolio,
            # ignore_cache=True,
        )

    DATA = fifo_portfolio.as_cannonical_data()
    print(DATA)
    DATA.to_csv("i365/fxblue.csv", index=False)
    # print(pd.read_csv("https://www.fxblue.com/users/alun/csv", skiprows=1))
