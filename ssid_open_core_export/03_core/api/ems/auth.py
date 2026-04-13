from dataclasses import dataclass

from fastapi import Header, HTTPException, status


@dataclass(frozen=True)
class Identity:
    subject: str


def get_current_identity(x_ssid_identity: str | None = Header(default=None, alias="X-SSID-Identity")) -> Identity:
    # Interim bridge until 14_zero_time_auth is exposed as a first-class web dependency.
    if x_ssid_identity is None or not x_ssid_identity.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authenticated identity",
        )
    return Identity(subject=x_ssid_identity.strip())
