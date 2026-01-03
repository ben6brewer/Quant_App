"""
NYSE market hours and trading calendar utilities.

Provides functions to determine if cached market data is current based on
NYSE trading hours, weekends, and holidays. Crypto tickers (24/7) are
handled separately from stocks.
"""

from __future__ import annotations

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

# NYSE timezone
NYSE_TZ = ZoneInfo("America/New_York")

# NYSE market hours (regular session)
NYSE_OPEN = time(9, 30)
NYSE_CLOSE = time(16, 0)

# Extended hours (pre-market and after-hours)
PREMARKET_OPEN = time(4, 0)
AFTERHOURS_CLOSE = time(20, 0)


def is_crypto_ticker(ticker: str) -> bool:
    """
    Check if a ticker is a cryptocurrency (trades 24/7).

    Args:
        ticker: Ticker symbol (e.g., "BTC-USD", "ETH-USDT", "AAPL")

    Returns:
        True if crypto ticker, False otherwise
    """
    ticker = ticker.upper()
    return ticker.endswith("-USD") or ticker.endswith("-USDT")


def easter_date(year: int) -> date:
    """
    Calculate Easter Sunday for a given year using the Anonymous Gregorian algorithm.

    Args:
        year: Year to calculate Easter for

    Returns:
        Date of Easter Sunday
    """
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
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_nyse_holidays(year: int) -> set[date]:
    """
    Get NYSE holidays for a given year.

    NYSE observes:
    - New Year's Day (Jan 1, or observed)
    - Martin Luther King Jr. Day (3rd Monday of Jan)
    - Presidents' Day (3rd Monday of Feb)
    - Good Friday (Friday before Easter)
    - Memorial Day (last Monday of May)
    - Juneteenth (June 19, or observed)
    - Independence Day (July 4, or observed)
    - Labor Day (1st Monday of Sep)
    - Thanksgiving (4th Thursday of Nov)
    - Christmas (Dec 25, or observed)

    Args:
        year: Year to get holidays for

    Returns:
        Set of holiday dates
    """
    holidays = set()

    def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
        """Get the Nth weekday (0=Mon, 6=Sun) of a month."""
        first = date(year, month, 1)
        first_weekday = first.weekday()
        days_until = (weekday - first_weekday) % 7
        return first + timedelta(days=days_until + 7 * (n - 1))

    def last_weekday(year: int, month: int, weekday: int) -> date:
        """Get the last weekday (0=Mon, 6=Sun) of a month."""
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        last_day = next_month - timedelta(days=1)
        days_back = (last_day.weekday() - weekday) % 7
        return last_day - timedelta(days=days_back)

    def observed(d: date) -> date:
        """Observe on Friday if Saturday, Monday if Sunday."""
        if d.weekday() == 5:  # Saturday
            return d - timedelta(days=1)
        elif d.weekday() == 6:  # Sunday
            return d + timedelta(days=1)
        return d

    # New Year's Day
    holidays.add(observed(date(year, 1, 1)))

    # MLK Day (3rd Monday of January)
    holidays.add(nth_weekday(year, 1, 0, 3))

    # Presidents' Day (3rd Monday of February)
    holidays.add(nth_weekday(year, 2, 0, 3))

    # Good Friday (Friday before Easter)
    holidays.add(easter_date(year) - timedelta(days=2))

    # Memorial Day (last Monday of May)
    holidays.add(last_weekday(year, 5, 0))

    # Juneteenth (June 19)
    holidays.add(observed(date(year, 6, 19)))

    # Independence Day (July 4)
    holidays.add(observed(date(year, 7, 4)))

    # Labor Day (1st Monday of September)
    holidays.add(nth_weekday(year, 9, 0, 1))

    # Thanksgiving (4th Thursday of November)
    holidays.add(nth_weekday(year, 11, 3, 4))

    # Christmas (December 25)
    holidays.add(observed(date(year, 12, 25)))

    return holidays


def is_nyse_trading_day(d: date) -> bool:
    """
    Check if a given date is a NYSE trading day.

    Args:
        d: Date to check

    Returns:
        True if trading day, False otherwise
    """
    # Weekend check
    if d.weekday() >= 5:
        return False

    # Holiday check
    holidays = get_nyse_holidays(d.year)
    if d in holidays:
        return False

    return True


def has_market_closed_today() -> bool:
    """
    Check if the NYSE has closed for today (past 4 PM ET).

    Returns:
        True if market has closed today, False otherwise
    """
    now_et = datetime.now(NYSE_TZ)
    return now_et.time() >= NYSE_CLOSE


def get_last_expected_trading_date() -> date:
    """
    Get the last date we should expect data for.

    For stocks:
    - If market has closed today and today is a trading day, return today
    - Otherwise, return the most recent past trading day

    Returns:
        The last expected trading date
    """
    now_et = datetime.now(NYSE_TZ)
    today = now_et.date()

    # If today is a trading day and market has closed, expect today's data
    if is_nyse_trading_day(today) and has_market_closed_today():
        return today

    # Otherwise, find the most recent past trading day
    d = today - timedelta(days=1)
    while not is_nyse_trading_day(d):
        d -= timedelta(days=1)

    return d


def is_stock_cache_current(last_cached_date: date) -> bool:
    """
    Check if stock cache is current (no new data expected).

    Args:
        last_cached_date: The last date in the cache

    Returns:
        True if cache is current, False if new data might be available
    """
    expected_date = get_last_expected_trading_date()
    return last_cached_date >= expected_date


def is_market_open_extended() -> bool:
    """
    Check if NYSE is open (including extended hours).

    Extended hours schedule:
    - Pre-market: 4:00 AM - 9:30 AM ET
    - Regular: 9:30 AM - 4:00 PM ET
    - After-hours: 4:00 PM - 8:00 PM ET

    Returns:
        True if current time is within extended trading hours
        AND today is a trading day (not weekend/holiday).
    """
    now_et = datetime.now(NYSE_TZ)
    today = now_et.date()

    # Check if today is a trading day
    if not is_nyse_trading_day(today):
        return False

    # Check if current time is within extended hours (4am - 8pm ET)
    current_time = now_et.time()
    return PREMARKET_OPEN <= current_time <= AFTERHOURS_CLOSE
