"""
GovAid API — Authentication Helpers & Base Utilities
=====================================================

This module handles the WSO2→Odoo authentication bridge using a shared
API key (X-GovAid-Api-Key header).

Architecture:
    External Client
        → [Bearer JWT] → WSO2 API Manager
            → validates token, strips Authorization header
            → injects X-GovAid-Api-Key: <shared_secret>
            → forwards to Odoo
        → [X-GovAid-Api-Key] → Odoo controller (@govaid_api_auth)
            → validates key against GOVAID_WSO2_API_KEY env var
            → runs business logic as technical user via sudo()

Security:
    - The shared secret MUST be set via GOVAID_WSO2_API_KEY environment variable
    - NEVER hardcode the key in source code
    - Rotate the key by updating the env var and WSO2 mediation sequence
    - The key should be a cryptographically random 32-byte hex string
      (generate with: openssl rand -hex 32)
"""
import functools
import json
import logging
import os

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared secret configuration
# WSO2 mediation sequence injects this header; Odoo validates it.
# The value is read from an environment variable for security.
# ---------------------------------------------------------------------------
GOVAID_API_KEY_HEADER = "X-GovAid-Api-Key"
_API_KEY = os.environ.get("GOVAID_WSO2_API_KEY", "")

if not _API_KEY:
    _logger.warning(
        "GovAid API: GOVAID_WSO2_API_KEY environment variable is NOT SET. "
        "All API requests will be rejected. Set this variable in docker-compose.yml"
    )


# ---------------------------------------------------------------------------
# Authentication Decorator
# ---------------------------------------------------------------------------

def govaid_api_auth(func):
    """
    Decorator that validates the shared WSO2→Odoo API key.

    Usage:
        @http.route("/govaid/v1/...", type="http", auth="none", ...)
        @govaid_api_auth
        def my_endpoint(self, **kwargs):
            ...

    The decorator must come AFTER @http.route.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        incoming_key = request.httprequest.headers.get(GOVAID_API_KEY_HEADER)

        if not _API_KEY:
            _logger.error(
                "GovAid API: Request rejected — GOVAID_WSO2_API_KEY not configured"
            )
            return _json_error(503, "Service Unavailable",
                               "API key not configured on server")

        if not incoming_key:
            _logger.warning(
                "GovAid API: Unauthorized — missing %s header from %s",
                GOVAID_API_KEY_HEADER,
                request.httprequest.remote_addr,
            )
            return _json_error(401, "Unauthorized",
                               f"Missing {GOVAID_API_KEY_HEADER} header")

        if incoming_key != _API_KEY:
            _logger.warning(
                "GovAid API: Unauthorized — invalid API key from %s",
                request.httprequest.remote_addr,
            )
            return _json_error(401, "Unauthorized", "Invalid API key")

        # Log the caller identity forwarded by WSO2 (for audit trail)
        caller = request.httprequest.headers.get("X-GovAid-Caller", "unknown")
        _logger.info(
            "GovAid API: Authorized request | caller=%s | path=%s | method=%s",
            caller,
            request.httprequest.path,
            request.httprequest.method,
        )

        return func(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Response Helpers
# ---------------------------------------------------------------------------

def _json_response(data, status=200):
    """Return a JSON HTTP response with the given data and status code."""
    return Response(
        json.dumps(data, default=str),  # default=str handles dates, Decimals, etc.
        status=status,
        content_type="application/json; charset=utf-8",
    )


def _json_error(status, error, message, details=None):
    """Return a standardized JSON error response."""
    body = {
        "error": error,
        "message": message,
        "status": status,
    }
    if details:
        body["details"] = details
    return Response(
        json.dumps(body),
        status=status,
        content_type="application/json; charset=utf-8",
    )


def _parse_json_body():
    """
    Parse the request body as JSON.
    Returns (body_dict, error_response) tuple.
    On success: (dict, None)
    On failure: (None, Response)
    """
    try:
        raw = request.httprequest.data
        if not raw:
            return {}, None
        return json.loads(raw), None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        _logger.warning("GovAid API: Invalid JSON body: %s", str(e))
        return None, _json_error(400, "Bad Request", "Request body must be valid JSON")
