import functools
import logging
import os
from datetime import datetime, timedelta

import jwt
from flask import jsonify, request, g

logger = logging.getLogger(__name__)


class AuthConfigError(RuntimeError):
    """Raised when authentication configuration is invalid."""


def _get_secret_key() -> str:
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise AuthConfigError("JWT_SECRET_KEY environment variable is not set")
    return secret


def generate_token(hours_valid: int = 12) -> str:
    """Generate a JWT token valid for the given number of hours."""
    now = datetime.utcnow()
    payload = {
        "iat": now,
        "exp": now + timedelta(hours=hours_valid),
        "sub": "authenticated_user",
    }
    token = jwt.encode(payload, _get_secret_key(), algorithm="HS256")
    return token


def decode_token(token: str):
    """Decode and validate a JWT token."""
    return jwt.decode(token, _get_secret_key(), algorithms=["HS256"])


def require_auth(view_func):
    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization token is missing"}), 401

        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token)
            g.jwt_payload = payload
        except AuthConfigError as exc:
            logger.error("Authentication configuration error: %s", exc)
            return jsonify({"error": str(exc)}), 500
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return view_func(*args, **kwargs)

    return wrapper
