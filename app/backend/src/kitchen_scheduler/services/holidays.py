"""Utility helpers for canton-specific public holidays."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable


@dataclass(frozen=True)
class Holiday:
    """Simple representation of a public holiday."""

    code: str
    date: date
    name: str
    localized_name: str


def _calculate_easter_sunday(year: int) -> date:
    """Return the Gregorian Easter Sunday for *year* using the Anonymous algorithm."""

    # Anonymous Gregorian algorithm (Meeus/Jones/Butcher)
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = 1 + (h + l - 7 * m + 114) % 31
    return date(year, month, day)


def _third_monday_of_september(year: int) -> date:
    """Return the date of the third Monday in September for *year*."""

    september_first = date(year, 9, 1)
    # Monday is weekday 0
    offset = (0 - september_first.weekday()) % 7
    first_monday = september_first + timedelta(days=offset)
    return first_monday + timedelta(weeks=2)


def get_vaud_public_holidays(year: int) -> list[Holiday]:
    """Return the list of public holidays observed in the Canton of Vaud for *year*."""

    easter = _calculate_easter_sunday(year)
    good_friday = easter - timedelta(days=2)
    easter_monday = easter + timedelta(days=1)
    ascension = easter + timedelta(days=39)
    whit_monday = easter + timedelta(days=50)
    federal_fast_monday = _third_monday_of_september(year)

    return [
        Holiday("new_years_day", date(year, 1, 1), "New Year's Day", "Nouvel An"),
        Holiday("berchtolds_day", date(year, 1, 2), "Berchtold Day", "Saint Berchtold"),
        Holiday("vaud_independence_day", date(year, 1, 24), "Vaud Independence Day", "Fête de l'Indépendance vaudoise"),
        Holiday("good_friday", good_friday, "Good Friday", "Vendredi saint"),
        Holiday("easter_monday", easter_monday, "Easter Monday", "Lundi de Pâques"),
        Holiday("ascension_day", ascension, "Ascension Day", "Ascension"),
        Holiday("whit_monday", whit_monday, "Whit Monday", "Lundi de Pentecôte"),
        Holiday("swiss_national_day", date(year, 8, 1), "Swiss National Day", "Fête nationale suisse"),
        Holiday("federal_fast_monday", federal_fast_monday, "Federal Fast Monday", "Lundi du Jeûne fédéral"),
        Holiday("christmas_day", date(year, 12, 25), "Christmas Day", "Noël"),
        Holiday("st_stephens_day", date(year, 12, 26), "St. Stephen's Day", "Saint Étienne"),
    ]


def iter_vaud_public_holidays(start_year: int, end_year: int) -> Iterable[Holiday]:
    """Yield holidays for Canton Vaud between *start_year* and *end_year* (inclusive)."""

    for year in range(start_year, end_year + 1):
        yield from get_vaud_public_holidays(year)


__all__ = ["Holiday", "get_vaud_public_holidays", "iter_vaud_public_holidays"]
