from __future__ import annotations

import pandas as pd
import yfinance as yf


_INTERVAL_MAP = {
    "daily": "1d",
    "weekly": "1wk",
    "monthly": "1mo",
    "yearly": "1y",
}


def fetch_price_history(
    ticker: str,
    period: str = "max",
    interval: str = "1d",
) -> pd.DataFrame:
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Ticker is empty.")

    interval_key = (interval or "1d").strip().lower()
    yf_interval = _INTERVAL_MAP.get(interval_key)
    resample_yearly = False
    if yf_interval == "1y":
        resample_yearly = True
        yf_interval = "1mo"  # fetch monthly and roll up to yearly

    df = yf.download(
        tickers=ticker,
        period=period,
        interval=yf_interval,
        auto_adjust=False,
        progress=False,
        threads=True,
    )

    if df is None or df.empty:
        raise ValueError(f"No data returned for ticker '{ticker}'.")

    # Sometimes yfinance returns MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    # If user asked for annually, resample to year bars (OHLCV)
    if resample_yearly:
        ohlc = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
        }
        if "Volume" in df.columns:
            ohlc["Volume"] = "sum"

        df = df.resample("YE").agg(ohlc).dropna(how="any")

    return df
