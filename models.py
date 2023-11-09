"""Application models"""

import datetime
from dataclasses import dataclass
from enum import Enum


class DataInputType(Enum):
    """Supported trades data input types"""

    FX_BLUE = "FxBlue CSV"
    MT5_TESTER = "MT5 tester XLSX"


@dataclass
class DataInput:
    """Data input"""

    input_type: DataInputType
    data_url: str


@dataclass
class DateFilter:
    """Optional date filter"""

    date_from: datetime.date
    date_to: datetime.date


@dataclass
class Settings:
    """Application settings"""

    data_input: DataInput
    comment_filter: str
    magic_filter: str
    currency_sym: str
    override_capital: bool
    assumed_capital: float
    date_filter: DateFilter
