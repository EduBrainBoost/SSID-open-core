"""FastAPI security dependencies for Admin API."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

ADMIN_ROLES = {"superadmin", "auditor", "operator", "viewer"}


def get_current_user(request: Request) -> dict:
    """Extract user from Authorization header. Fail-closed."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    token = auth[7:]
    try:
        from .zerotime import decode_jwt_payload

        payload = decode_jwt_payload(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None

    role = payload.get("role", "")
    if role not in ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{role}' not authorized")

    return {"sub": payload.get("sub", "unknown"), "role": role}


def require_role(*roles: str):
    """Dependency factory: require one of the specified roles."""

    def _check(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return _check
