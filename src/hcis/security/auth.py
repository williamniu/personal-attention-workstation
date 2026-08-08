from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Header, HTTPException

from hcis.settings import get_settings


def require_api_token(
    authorization: Annotated[str | None, Header()] = None,
    x_api_token: Annotated[str | None, Header()] = None,
) -> None:
    supplied = x_api_token
    if authorization and authorization.startswith("Bearer "):
        supplied = authorization.removeprefix("Bearer ")
    expected = get_settings().api_token
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Valid local API token required")
