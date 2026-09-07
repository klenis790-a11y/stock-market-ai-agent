import os

from openai import APIConnectionError, APIStatusError, OpenAI, OpenAIError


MODEL = "gpt-5.6-terra"


def request_text(*, input: str, max_output_tokens: int, **options) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        raise RuntimeError("OPENAI_API_KEY must be configured.")

    try:
        with OpenAI(
            api_key=api_key,
            base_url="https://api.openai.com/v1",
            timeout=30.0,
            max_retries=0,
        ) as client:
            response = client.responses.create(
                model=MODEL,
                input=input,
                max_output_tokens=max_output_tokens,
                store=False,
                **options,
            )
    except APIStatusError as error:
        raise RuntimeError(
            f"OpenAI API HTTP error: {error.status_code} ({type(error).__name__})."
        ) from None
    except APIConnectionError:
        raise RuntimeError("OpenAI connection failed or timed out.") from None
    except OpenAIError:
        raise RuntimeError("OpenAI request failed.") from None

    text = response.output_text.strip()
    if not text:
        raise RuntimeError("OpenAI returned no text.")
    return text


def test_openai_connection() -> str:
    return request_text(input="Reply with only OK.", max_output_tokens=16)
