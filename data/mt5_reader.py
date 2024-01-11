"""Reader that reads from MT5 strategy tester XLSX report"""

import os
import re

import pandas as pd
import requests
from data.base import FifoPortfolio, PosType, Trade, get_temp_file, mkdirs

ID_REGEXP = re.compile("/d/([^/]+)/")
REQUEST_TIMEOUT = 20


def _get_file_id(share_url: str) -> str:
    """Parse the file ID from a Google Drive/Sheets URL"""
    found_groups = ID_REGEXP.findall(share_url)
    if found_groups:
        file_id = found_groups[0]
        return file_id
    return None


def _to_file_download_url(file_id: str) -> str:
    """Converts a Google Sheets URL that is shared to a download URL"""
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def _get_pos_type(deal: pd.Series) -> PosType:
    """Converts MT5 deal type to PosType"""
    if deal.Type == "buy":
        return PosType.BUY
    if deal.Type == "sell":
        return PosType.SELL
    raise ValueError(f"Invalid deal type: {deal.Type}")


MT5_TESTER_COL_TYPES = {
    "Time": "datetime64[ns]",
    "Volume": "float64",
    "Profit": "float64",
    "Price": "float64",
    "Commission": "float64",
}


class Mt5Reader:
    """Reader that reads from MT5 strategy tester XLSX report"""

    def __init__(self, share_url: str, ignore_cache=False):
        self._file_id = _get_file_id(share_url)
        self._fifo_portfolio = FifoPortfolio()
        self._ignore_cache = ignore_cache

        if not self._file_id:
            raise ValueError(f"Invalid URL: {share_url}")
        self._load()

    def _load(self):
        """Loads the XLSX file from the URL into a dataframe"""
        cache_file = get_temp_file(Mt5Reader, self._file_id)

        if not self._ignore_cache:
            # try read from cache
            if os.path.isfile(cache_file):
                print("read from cache " + cache_file)
                self._data = pd.read_csv(cache_file)
                self._data.Time = pd.to_datetime(self._data.Time)
                return

        xlsx_bytes = requests.get(
            _to_file_download_url(self._file_id), timeout=REQUEST_TIMEOUT
        ).content
        self._data = pd.read_excel(xlsx_bytes)

        if "Type" not in self._data:
            # try to use the first row as column names
            self._data.columns = self._data.iloc[0, :].values
            self._data = self._data.drop(0).reset_index(drop=True)
        if "Type" not in self._data:
            # try to find the "Deals" block
            deals_start_mask = self._data.iloc[:, 0] == "Deals"
            deals_block_start = self._data[deals_start_mask].index[0]

            self._data.columns = self._data.iloc[deals_block_start + 1, :].values
            self._data = self._data.iloc[(deals_block_start + 2) :, :]

        if "Type" not in self._data.columns:
            raise ValueError("Bad spread sheet format")
        self._data = self._data.dropna(subset=["Type"]).reset_index(drop=True)

        self._data = self._data.astype(MT5_TESTER_COL_TYPES)

        if not self._ignore_cache:
            # cache results
            mkdirs(cache_file)
            self._data.to_csv(cache_file, index=False)

    def get_cannoncial_data(self):
        """Gets data in FxBlue format"""
        for _, row in self._data.iterrows():
            self._process_deal(row)

        if self._fifo_portfolio.has_open_positions():
            raise ValueError("Some positions are still open")

        return self._fifo_portfolio.as_cannonical_data()

    def _process_deal(self, deal: pd.Series):
        """Process deal record from MT5 stategy tester"""
        if deal.Type == "balance":
            self._fifo_portfolio.deposit(deal.Time, deal.Profit)
        elif deal.Direction == "in":
            self._fifo_portfolio.open_position(
                Trade(
                    time=deal.Time,
                    symbol=deal.Symbol,
                    pos_type=_get_pos_type(deal),
                    volume=deal.Volume,
                    price=deal.Price,
                    comment=deal.Comment,
                    swap=deal.Swap,
                    commission=deal.Commission,
                    profit=deal.Profit,
                )
            )
        elif deal.Direction == "out":
            self._fifo_portfolio.close_position(
                Trade(
                    time=deal.Time,
                    symbol=deal.Symbol,
                    pos_type=_get_pos_type(deal).inverse(),
                    volume=deal.Volume,
                    price=deal.Price,
                    comment=deal.Comment,
                    swap=deal.Swap,
                    commission=deal.Commission,
                    profit=deal.Profit,
                )
            )


if __name__ == "__main__":
    # URL = "https://docs.google.com/spreadsheets/d/1_zkzXwMQ6z_D2RjEDtowunBgBR7kBQde/edit?usp=sharing&ouid=100387466746717550961&rtpof=true&sd=true"
    # URL = "https://docs.google.com/spreadsheets/d/1xyagwvas0dh7gOzABCZ6bGzElP-zboZ2/edit?usp=sharing&ouid=108957322456978477968&rtpof=true&sd=true"
    URL = "https://docs.google.com/spreadsheets/d/1lMyYAGhBRASp0GcoeytLBpOPGwNvzB3I/edit?usp=sharing&ouid=108957322456978477968&rtpof=true&sd=true"
    DATA = Mt5Reader(
        URL,
        # ignore_cache=True,
    ).get_cannoncial_data()
    print(DATA)
    # print(pd.read_csv("https://www.fxblue.com/users/alun/csv", skiprows=1))
