import json
import os
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def get_company_overview(ticker: str) -> dict:
    return _request("OVERVIEW", ticker)


def get_income_statement(ticker: str) -> dict:
    return _request("INCOME_STATEMENT", ticker)


def _request(function: str, ticker: str) -> dict:
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key or not api_key.strip():
        raise RuntimeError("ALPHA_VANTAGE_API_KEY must be configured.")

    query = urlencode({"function": function, "symbol": ticker, "apikey": api_key})
    try:
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
            raise RuntimeError(
                f"Alpha Vantage returned {message_key}: API error or request limit; "
                "check API access and rate limits."
            )
    if not data:
        raise RuntimeError(f"Alpha Vantage returned no data for {function}.")
    return data
