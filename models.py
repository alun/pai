"""Application models"""

from dataclasses import dataclass


@dataclass
class Settings:
    """Application settings"""

    data_url: str
    comment_filter: str
    magic_filter: str
    currency_sym: str
    override_capital: bool
    assumed_capital: float
