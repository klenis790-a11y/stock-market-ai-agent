"""Local credential bootstrap into the environment consumed by existing clients."""
import os
from pathlib import Path
import shlex

CREDENTIAL_NAMES = ('ALPHA_VANTAGE_API_KEY', 'OPENAI_API_KEY')


def load_local_environment(path: Path | None = None) -> None:
    """Load literal KEY=value credentials without executing shell code.

    Existing environment entries win, including empty entries (fail closed).
    Supports optional export, quotes and comments; no expansion or shell execution.
    Missing file is allowed: existing client credential checks remain authoritative.
    """
    path = path if path is not None else Path(__file__).resolve().parents[1] / '.env'
    try:
        content = path.read_text()
    except FileNotFoundError:
        return
    except (OSError, UnicodeError):
        raise RuntimeError('Local environment configuration could not be read.') from None
    pending = {}
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, separator, value = line.partition('=')
        key = key.strip()
        if key not in CREDENTIAL_NAMES or not separator or key in os.environ:
            continue
        try:
            tokens = shlex.split(value, comments=True, posix=True)
        except ValueError:
            raise RuntimeError('Local credential configuration has invalid syntax.') from None
        if len(tokens) > 1 or '$' in value or '`' in value:
            raise RuntimeError('Local credentials must use literal values.')
        pending[key] = tokens[0] if tokens else ''
    for key, value in pending.items():
        os.environ.setdefault(key, value)
