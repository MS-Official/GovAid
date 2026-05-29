"""
GovAid API — Beneficiaries Endpoints
=====================================

Endpoints:
    GET  /govaid/v1/beneficiaries          — list with optional filters
    POST /govaid/v1/beneficiaries          — create a new beneficiary
    GET  /govaid/v1/beneficiaries/<id>     — get single beneficiary

All endpoints require a valid X-GovAid-Api-Key header (injected by WSO2).
Authentication to Odoo is done via sudo() as a technical service account.
"""
import logging

from odoo import http
from odoo.http import request
from .main import govaid_api_auth, _json_response, _json_error, _parse_json_body

_logger = logging.getLogger(__name__)

# Fields to expose — extend this list as your data model grows
BENEFICIARY_SAFE_FIELDS = [
    "id", "name", "gender", "birthdate", "phone", "email", "active",
]


class GovAidBeneficiariesController(http.Controller):

    # ──────────────────────────────────────────────────────────────────────
    # GET /govaid/v1/beneficiaries
    # Query params: limit, offset, name, gender
    # ──────────────────────────────────────────────────────────────────────
    @http.route(
        "/govaid/v1/beneficiaries",
        type="http",
        auth="none",
        methods=["GET"],
        csrf=False,
        cors="*",
        save_session=False,
    )
    @govaid_api_auth
    def list_beneficiaries(self, **kwargs):
        """
        List beneficiaries from the OpenG2P social registry.
        Supports pagination and filtering.

        Query Parameters:
            limit   (int, default=50)  — max records to return
            offset  (int, default=0)   — pagination offset
            name    (str, optional)    — case-insensitive name filter
            gender  (str, optional)    — 'male' | 'female' | 'other'
        """
        # Parse and validate query parameters
        try:
            limit  = min(int(kwargs.get("limit", 50)), 200)   # cap at 200
            offset = max(int(kwargs.get("offset", 0)), 0)
        except (ValueError, TypeError):
            return _json_error(400, "Bad Request", "limit and offset must be integers")

        name   = kwargs.get("name")
        gender = kwargs.get("gender")

        # Build domain filter
        domain = [("is_registrant", "=", True)]
        if name:
            domain.append(("name", "ilike", name))
        if gender:
            domain.append(("gender", "=", gender))

        try:
            env        = request.env["g2p.registrant"].sudo()
            total      = env.search_count(domain)
            registrants = env.search(domain, limit=limit, offset=offset, order="id desc")

            return _json_response({
                "total":   total,
                "count":   len(registrants),
                "offset":  offset,
                "limit":   limit,
                "results": [_format_beneficiary(r) for r in registrants],
            })
        except Exception as e:
            _logger.error("GovAid API: list_beneficiaries failed: %s", str(e), exc_info=True)
            return _json_error(500, "Internal Server Error", "Failed to retrieve beneficiaries")

    # ──────────────────────────────────────────────────────────────────────
    # POST /govaid/v1/beneficiaries
    # ──────────────────────────────────────────────────────────────────────
    @http.route(
        "/govaid/v1/beneficiaries",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        cors="*",
        save_session=False,
    )
    @govaid_api_auth
    def create_beneficiary(self, **kwargs):
        """
        Create a new beneficiary in the OpenG2P social registry.

        Request Body (JSON):
            name        (str, required)  — full legal name
            gender      (str, optional)  — 'male' | 'female' | 'other'
            birthdate   (str, optional)  — 'YYYY-MM-DD'
            phone       (str, optional)  — phone number with country code
            email       (str, optional)  — email address

        Returns: 201 Created with the new beneficiary record
        """
        body, err = _parse_json_body()
        if err:
            return err

        # Validate required fields
        required = ["name"]
        missing = [f for f in required if not body.get(f)]
        if missing:
            return _json_error(
                400, "Bad Request",
                f"Missing required fields: {missing}",
                {"required_fields": required},
            )

        vals = {
            "name":          body["name"].strip(),
            "gender":        body.get("gender"),
            "birthdate":     body.get("birthdate"),
            "phone":         body.get("phone"),
            "email":         body.get("email"),
            "is_registrant": True,
            "active":        True,
        }

        # Remove None values to use Odoo defaults
        vals = {k: v for k, v in vals.items() if v is not None}

        try:
            registrant = request.env["g2p.registrant"].sudo().create(vals)
            _logger.info(
                "GovAid API: Created beneficiary id=%s name='%s'",
                registrant.id, registrant.name,
            )
            return _json_response(_format_beneficiary(registrant), status=201)
        except Exception as e:
            _logger.error("GovAid API: create_beneficiary failed: %s", str(e), exc_info=True)
            return _json_error(500, "Internal Server Error", f"Failed to create beneficiary: {str(e)}")

    # ──────────────────────────────────────────────────────────────────────
    # GET /govaid/v1/beneficiaries/<beneficiary_id>
    # ──────────────────────────────────────────────────────────────────────
    @http.route(
        "/govaid/v1/beneficiaries/<int:beneficiary_id>",
        type="http",
        auth="none",
        methods=["GET"],
        csrf=False,
        cors="*",
        save_session=False,
    )
    @govaid_api_auth
    def get_beneficiary(self, beneficiary_id, **kwargs):
        """
        Retrieve a single beneficiary by their Odoo record ID.

        Path Parameters:
            beneficiary_id (int) — the Odoo record ID of the registrant

        Returns: 200 OK with beneficiary details, or 404 if not found
        """
        try:
            registrant = request.env["g2p.registrant"].sudo().browse(beneficiary_id)
            if not registrant.exists():
                return _json_error(
                    404, "Not Found",
                    f"Beneficiary with id={beneficiary_id} does not exist",
                )
            return _json_response(_format_beneficiary(registrant))
        except Exception as e:
            _logger.error("GovAid API: get_beneficiary failed: %s", str(e), exc_info=True)
            return _json_error(500, "Internal Server Error", "Failed to retrieve beneficiary")


# ──────────────────────────────────────────────────────────────────────────
# Data Formatting — controls what fields are exposed in API responses
# Add/remove fields here based on your data governance requirements
# ──────────────────────────────────────────────────────────────────────────

def _format_beneficiary(registrant):
    """
    Normalize a g2p.registrant record into a clean, safe API response dict.

    Data masking rules:
        - Full bank account numbers are NEVER returned
        - National ID shows only last 4 characters
        - Internal Odoo fields (write_uid, create_uid, etc.) are excluded
    """
    r = registrant
    return {
        "id":             r.id,
        "name":           r.name,
        "gender":         r.gender or None,
        "birthdate":      str(r.birthdate) if r.birthdate else None,
        "phone":          r.phone or None,
        "email":          r.email or None,
        "active":         r.active,
        # Presence indicators — never expose raw sensitive data
        "has_bank_account": bool(getattr(r, "bank_ids", None)),
        "has_id_document":  bool(getattr(r, "reg_ids", None)),
        # Audit fields
        "created_at":     str(r.create_date) if r.create_date else None,
        "updated_at":     str(r.write_date) if r.write_date else None,
    }
