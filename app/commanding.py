from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class CommandOutcome:
    status: int = 200
    payload: Optional[Any] = None
    use_state: bool = True


def ok():
    return CommandOutcome()


def custom(payload, status=200):
    return CommandOutcome(status=status, payload=payload, use_state=False)


def error(code, status, **extra):
    payload = {"error": code}
    payload.update(extra)
    return CommandOutcome(status=status, payload=payload, use_state=False)


def finalize_command(c, outcome):
    if outcome.status >= 400:
        c.rollback()
        return False
    c.commit()
    return True
