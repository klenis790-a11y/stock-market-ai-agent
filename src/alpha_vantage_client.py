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


# Fixed diagnostic vocabulary: never derive log labels from request parameters or bodies.
_OPERATIONS = {
    'OVERVIEW': 'company_overview', 'GLOBAL_QUOTE': 'global_quote',
    'INCOME_STATEMENT': 'income_statement', 'BALANCE_SHEET': 'balance_sheet',
    'CASH_FLOW': 'cash_flow', 'EARNINGS': 'earnings',
    'NEWS_SENTIMENT': 'news_sentiment', 'EARNINGS_CALL_TRANSCRIPT': 'earnings_call_transcript',
    'TIME_SERIES_DAILY_ADJUSTED': 'daily_adjusted', 'TIME_SERIES_DAILY': 'daily_raw',
}


def _request(function, ticker=None, *, reject_duplicate_keys=False, **params):
    try:
        return _request_impl(function, ticker, reject_duplicate_keys=reject_duplicate_keys, **params)
    except RuntimeError as error:
        message = str(error)
        classification = 'MALFORMED_RESPONSE'
        for prefix, kind in (
            ('Alpha Vantage Error Message:', 'ERROR_MESSAGE'),
            ('Alpha Vantage Information:', 'INFORMATION'),
            ('Alpha Vantage Note:', 'NOTE'),
            ('Alpha Vantage HTTP error:', 'HTTP_ERROR'),
            ('Alpha Vantage network request', 'NETWORK_ERROR'),
            ('Alpha Vantage returned no data', 'EMPTY_RESPONSE'),
            ('ALPHA_VANTAGE_API_KEY must', 'CONFIGURATION_ERROR'),
        ):
            if message.startswith(prefix):
                classification = kind
                break
        error.provider_operation = _OPERATIONS.get(function, 'unknown')
        error.provider_function = function if function in _OPERATIONS else 'UNKNOWN'
        error.provider_response_type = classification
        # Also identifies optional failures swallowed by the existing pipeline.
        import logging
        logging.getLogger(__name__).error(
            'Alpha Vantage retrieval failed operation=%s function=%s provider_response_type=%s',
            error.provider_operation, error.provider_function, classification)
        raise


def _request_impl(function: str, ticker: str | None = None, *, reject_duplicate_keys: bool = False, **params: str | int) -> dict:
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key or not api_key.strip():
        raise RuntimeError("ALPHA_VANTAGE_API_KEY must be configured.")

    if ticker is not None:
        params["symbol"] = ticker
    query = urlencode({**params, "function": function, "apikey": api_key})
    try:
        _pace_request()
        with urlopen(f"https://www.alphavantage.co/query?{query}", timeout=30) as response:
            data = (json.load(response, object_pairs_hook=_unique_json_object)
                    if reject_duplicate_keys else json.load(response))
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


def _unique_json_object(pairs):
    """Reject duplicates before a dict can silently discard an earlier daily row."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key.')
        result[key] = value
    return result


def get_daily_raw(ticker: str) -> dict:
    """V0.7 raw OHLCV only. Full history; strict decoding; existing pacing/no retries."""
    return _request('TIME_SERIES_DAILY', ticker, outputsize='full', reject_duplicate_keys=True)
