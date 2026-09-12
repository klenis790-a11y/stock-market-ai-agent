import json
import os
import re
import time
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


MIN_REQUEST_INTERVAL = 1.0
_last_request_time: float | None = None


def _pace_request() -> None:
    """Pace this process's sequential requests; does not track the daily quota."""
    global _last_request_time
    if _last_request_time is not None:
        remaining = MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request_time)
        if remaining > 0:
            time.sleep(remaining)
    _last_request_time = time.monotonic()


def get_earnings_call_transcript(ticker: str, quarter: str) -> dict:
    if not isinstance(quarter, str) or re.fullmatch(r"[0-9]{4}Q[1-4]", quarter) is None:
        raise ValueError("quarter must use YYYYQ1, YYYYQ2, YYYYQ3, or YYYYQ4 format.")
    return _request("EARNINGS_CALL_TRANSCRIPT", ticker, quarter=quarter)


def get_global_quote(ticker: str) -> dict:
    """Retrieve the latest available quote; no real-time entitlement is assumed."""
    return _request("GLOBAL_QUOTE", ticker)


def get_company_overview(ticker: str) -> dict:
    return _request("OVERVIEW", ticker)


def get_income_statement(ticker: str) -> dict:
    return _request("INCOME_STATEMENT", ticker)


def get_balance_sheet(ticker: str) -> dict:
    return _request("BALANCE_SHEET", ticker)


def get_cash_flow(ticker: str) -> dict:
    return _request("CASH_FLOW", ticker)


def get_earnings(ticker: str) -> dict:
    return _request("EARNINGS", ticker)


def get_news_sentiment(ticker: str) -> dict:
    return _request("NEWS_SENTIMENT", tickers=ticker, limit=10, sort="LATEST")


def _request(function: str, ticker: str | None = None, **params: str | int) -> dict:
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key or not api_key.strip():
        raise RuntimeError("ALPHA_VANTAGE_API_KEY must be configured.")

    if ticker is not None:
        params["symbol"] = ticker
    query = urlencode({**params, "function": function, "apikey": api_key})
    try:
        _pace_request()
        with urlopen(f"https://www.alphavantage.co/query?{query}", timeout=30) as response:
            data = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"Alpha Vantage HTTP error: {error.code}.") from None
    except (URLError, OSError, HTTPException):
        raise RuntimeError("Alpha Vantage network request failed or timed out.") from None
    except (ValueError, UnicodeError):
        raise RuntimeError("Alpha Vantage returned invalid JSON.") from None

    if not isinstance(data, dict):
        raise RuntimeError("Alpha Vantage returned an unexpected response format.")
    for message_key in ("Error Message", "Note", "Information"):
        if message_key in data:
            message = data[message_key]
            if not isinstance(message, str):
                message = "Non-text API error message."
            # Provider messages may echo credentials. Never render request URLs.
            message = re.sub(r"https?://\S+", "[URL REDACTED]", message, flags=re.I)
            secrets = [
                value for name, value in os.environ.items()
                if value and any(marker in name.upper() for marker in (
                    "KEY", "TOKEN", "SECRET", "PASSWORD", "AUTHORIZATION",
                ))
            ]
            for secret in sorted(secrets, key=len, reverse=True):
                message = message.replace(secret, "[REDACTED]")
            raise RuntimeError(f"Alpha Vantage {message_key}: {message}")
    if not data:
        raise RuntimeError(f"Alpha Vantage returned no data for {function}.")
    return data


def get_daily_adjusted(ticker: str) -> dict:
    """One full historical series supplies both exact evaluation sessions; no retries."""
    return _request('TIME_SERIES_DAILY_ADJUSTED', ticker, outputsize='full')
