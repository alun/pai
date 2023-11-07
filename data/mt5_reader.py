"""Reader that reads from MT5 strategy tester XLSX report"""

import os
import re
import tempfile
from dataclasses import dataclass
from enum import Enum
from typing import List

import pandas as pd
import requests

ID_REGEXP = re.compile("/d/([^/]+)/")
REQUEST_TIMEOUT = 20

CANONICAL_COL_ORDER = [
    "Type",
    "Ticket",
    "Symbol",
    "Lots",
    "Buy/sell",
    "Open price",
    "Close price",
    "Open time",
    "Close time",
    "Profit",
    "Swap",
    "Commission",
    "Net profit",
    "T/P",
    "S/L",
    "Magic number",
    "Order comment",
]


class PosType(Enum):
    """Type of position"""

    BUY = "Buy"
    SELL = "Sell"

    def inverse(self):
        """Returns the inverse of the position type"""
        if self == PosType.BUY:
            return PosType.SELL
        return PosType.BUY


@dataclass
class Position:
    """Class to track a position"""

    id: int
    symbol: str
    volume: float
    open_time: pd.Timestamp
    open_price: float
    type: PosType
    comment: str = ""
    close_time: pd.Timestamp = None
    close_price: float = None
    swap: float = 0
    commission: float = 0
    profit: float = 0

    def is_open(self) -> bool:
        """Returns true if the position is still open"""
        return self.close_time is None


@dataclass
class Deposit:
    """Deposit/withdrawal transaction"""

    id: int
    time: pd.Timestamp
    amount: float


class FifoPortfolio:
    """Class to track a FIFO portfolio"""

    def __init__(self):
        self._deposits: List[Deposit] = []
        self._opened_positions: List[Position] = []
        self._closed_positions: List[Position] = []
        self._last_id: int = 0

    def has_open_positions(self):
        """Returns true if there are still open positions"""
        return len(self._opened_positions) > 0

    def deposit(self, time: pd.Timestamp, amount: float):
        """Register a deposit/withdrawal transaction"""
        self._last_id += 1
        self._deposits.append(Deposit(id=self._last_id, time=time, amount=amount))

    def open_position(
        self,
        time: pd.Timestamp,
        symbol: str,
        pos_type: PosType,
        volume: float,
        price: float,
        comment: str = None,
        swap: float = 0,
        commission: float = 0,
        profit: float = 0,
    ):
        """Opens a position"""
        self._last_id += 1
        self._opened_positions.append(
            Position(
                id=self._last_id,
                open_time=time,
                symbol=symbol,
                type=pos_type,
                volume=volume,
                open_price=price,
                comment="" if pd.isna(comment) else comment,
                swap=swap,
                commission=commission,
                profit=profit,
            )
        )

    def close_position(
        self,
        time: pd.Timestamp,
        symbol: str,
        pos_type: PosType,
        volume: float,
        price: float,
        comment: str = None,
        swap: float = 0,
        commission: float = 0,
        profit: float = 0,
    ):
        """Closes a position"""
        opened = [
            pos
            for pos in self._opened_positions
            if pos.symbol == symbol and pos.type == pos_type and pos.volume == volume
        ]
        if not opened:
            raise ValueError(
                f"No open position for symbol: {symbol} and type: {pos_type} and volume: {volume}"
            )

        pos = opened[0]
        self._opened_positions.remove(pos)

        # if pos.volume != volume:
        #     raise ValueError("Partial close is not yet supported")

        pos.close_time = time
        pos.close_price = price
        if not pd.isna(comment):
            pos.comment = pos.comment + f" [{comment}]"
        pos.swap += swap
        pos.commission += commission
        pos.profit += profit

        self._closed_positions.append(pos)

    def as_cannonical_data(self) -> pd.DataFrame:
        """Returns the data in cannonical (FxBlue) format"""
        deposits = pd.DataFrame(
            [
                [
                    "Deposit",
                    tx.id,
                    tx.amount,
                    tx.time,
                    tx.time,
                    "Deposit",
                    0,
                    0,
                    0,
                    0,
                    0,
                ]
                for tx in self._deposits
            ],
            columns=[
                "Type",
                "Ticket",
                "Profit",
                "Open time",
                "Close time",
                "Order comment",
                "Lots",
                "Open price",
                "Close price",
                "Swap",
                "Commission",
            ],
        )

        positions = pd.DataFrame(
            [
                [
                    "Closed position",
                    pos.id,
                    pos.symbol,
                    pos.volume,
                    pos.type.value,
                    pos.open_price,
                    pos.close_price,
                    pos.open_time,
                    pos.close_time,
                    pos.comment,
                    pos.swap,
                    pos.commission,
                    pos.profit,
                ]
                for pos in self._closed_positions
            ],
            columns=[
                "Type",
                "Ticket",
                "Symbol",
                "Lots",
                "Buy/sell",
                "Open price",
                "Close price",
                "Open time",
                "Close time",
                "Order comment",
                "Swap",
                "Commission",
                "Profit",
            ],
        )
        result = pd.concat([deposits, positions]).sort_values(by="Ticket")
        result["Net profit"] = result.Profit + result.Swap + result.Commission
        result["T/P"] = result["S/L"] = 0
        result["Magic number"] = 0

        return result[CANONICAL_COL_ORDER]


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


def _to_csv_download_url(file_id: str, sheet="Sheet1") -> str:
    """Converts a Google Sheets URL to a CSV download URL"""
    return f"https://docs.google.com/spreadsheets/d/{file_id}/gviz/tq?tqx=out:csv&sheet={sheet}"


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
        cache_file = os.path.join(
            tempfile.gettempdir(), "mt5_reader", f"mt5_{self._file_id}.csv"
        )

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
            # try to drop the first row
            self._data = pd.read_excel(xlsx_bytes, skiprows=1)
        if "Type" not in self._data:
            # try to find the "Deals" block
            deals_start_mask = self._data.iloc[:, 0] == "Deals"
            deals_block_start = self._data[deals_start_mask].index[0]
            columns = self._data.iloc[deals_block_start + 1, :].values

            if "Type" not in columns:
                raise ValueError("Could not find 'Type' column")

            self._data = self._data.iloc[(deals_block_start + 2) :, :]
            self._data.columns = columns

            self._data = self._data.dropna(subset=["Type"]).reset_index(drop=True)

        self._data = self._data.astype(MT5_TESTER_COL_TYPES)

        if not self._ignore_cache:
            # cache results
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
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
                deal.Time,
                deal.Symbol,
                _get_pos_type(deal),
                deal.Volume,
                deal.Price,
                deal.Comment,
                deal.Swap,
                deal.Commission,
                deal.Profit,
            )
        elif deal.Direction == "out":
            self._fifo_portfolio.close_position(
                deal.Time,
                deal.Symbol,
                _get_pos_type(deal).inverse(),
                deal.Volume,
                deal.Price,
                deal.Comment,
                deal.Swap,
                deal.Commission,
                deal.Profit,
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
    print(pd.read_csv("https://www.fxblue.com/users/alun/csv", skiprows=1))
