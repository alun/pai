"""Base utilities for data readers"""

import json
import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from typing import List

import pandas as pd

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
class Trade:
    """A trade that opens or closes a position"""

    time: pd.Timestamp
    symbol: str
    pos_type: PosType
    volume: float
    price: float
    comment: str = None
    swap: float = 0
    commission: float = 0
    profit: float = 0


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
        trade: Trade,
    ):
        """Opens a position"""
        self._last_id += 1
        self._opened_positions.append(
            Position(
                id=self._last_id,
                open_time=trade.time,
                symbol=trade.symbol,
                type=trade.pos_type,
                volume=trade.volume,
                open_price=trade.price,
                comment="" if pd.isna(trade.comment) else trade.comment,
                swap=trade.swap,
                commission=trade.commission,
                profit=0 if pd.isna(trade.profit) else trade.profit,
            )
        )

    def close_position(
        self,
        trade: Trade,
    ):
        """Closes a position"""
        opened = [
            pos
            for pos in self._opened_positions
            if pos.symbol == trade.symbol
            and pos.type == trade.pos_type
            and pos.volume == trade.volume
        ]
        if not opened:
            raise ValueError(
                f"No open position for symbol: {trade.symbol} and type: {trade.pos_type} and volume: {trade.volume}"
            )

        pos = opened[0]
        self._opened_positions.remove(pos)

        # if pos.volume != volume:
        #     raise ValueError("Partial close is not yet supported")

        pos.close_time = trade.time
        pos.close_price = trade.price
        if not pd.isna(trade.comment):
            pos.comment = pos.comment + f" [{trade.comment}]"
        pos.swap += trade.swap
        pos.commission += trade.commission
        pos.profit += trade.profit

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

        return result[CANONICAL_COL_ORDER].reset_index(drop=True)


def get_temp_file(client, prefix: str, suffix: str = "csv") -> str:
    """Returns a temp file path"""
    return os.path.join(
        tempfile.gettempdir(),
        client.__name__,
        f"{prefix}.{suffix}",
    )


def mkdirs(file: str):
    """Creates directories path for the given file"""
    os.makedirs(os.path.dirname(file), exist_ok=True)


def load_json(file_path: str):
    """Loads JSON from file"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(file_path: str, data: dict):
    """Saves JSON to file"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data))
