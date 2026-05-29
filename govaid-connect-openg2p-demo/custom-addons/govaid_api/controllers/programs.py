"""
GovAid API — Programs & Enrollment Endpoints
=============================================

Endpoints:
    POST /govaid/v1/programs/<programId>/enroll  — enroll a beneficiary in a program
    GET  /govaid/v1/programs                     — list active programs
"""
import logging

from odoo import http
from odoo.http import request
from .main import govaid_api_auth, _json_response, _json_error, _parse_json_body

_logger = logging.getLogger(__name__)


class GovAidProgramsController(http.Controller):

    # ──────────────────────────────────────────────────────────────────────
    # GET /govaid/v1/programs
    # ──────────────────────────────────────────────────────────────────────
    @http.route(
        "/govaid/v1/programs",
        type="http",
        auth="none",
        methods=["GET"],
        csrf=False,
        cors="*",
        save_session=False,
    )
    @govaid_api_auth
    def list_programs(self, **kwargs):
        """
        List all active aid programs in the system.

        Returns: 200 OK with list of programs
        """
        try:
            programs = request.env["g2p.program"].sudo().search(
                [("state", "=", "active")],
                order="name asc",
            )
            return _json_response({
                "count": len(programs),
                "programs": [{
                    "id":          p.id,
                    "name":        p.name,
                    "description": p.description or None,
                    "state":       p.state,
                } for p in programs],
            })
        except Exception as e:
            _logger.error("GovAid API: list_programs failed: %s", str(e), exc_info=True)
            return _json_error(500, "Internal Server Error", "Failed to retrieve programs")

    # ──────────────────────────────────────────────────────────────────────
    # POST /govaid/v1/programs/<programId>/enroll
    # ──────────────────────────────────────────────────────────────────────
    @http.route(
        "/govaid/v1/programs/<int:program_id>/enroll",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        cors="*",
        save_session=False,
    )
    @govaid_api_auth
    def enroll_beneficiary(self, program_id, **kwargs):
        """
        Enroll a beneficiary in a specific aid program.

        Path Parameters:
            program_id (int) — Odoo record ID of the program

        Request Body (JSON):
            beneficiary_id (int, required) — Odoo record ID of the beneficiary

        Returns:
            201 Created  — newly created membership record
            409 Conflict — beneficiary already enrolled
            404 Not Found — program or beneficiary not found
        """
        body, err = _parse_json_body()
        if err:
            return err

        beneficiary_id = body.get("beneficiary_id")
        if not beneficiary_id:
            return _json_error(400, "Bad Request", "beneficiary_id is required in request body")

        # Validate program exists
        program = request.env["g2p.program"].sudo().browse(program_id)
        if not program.exists():
            return _json_error(404, "Not Found", f"Program with id={program_id} does not exist")

        if program.state != "active":
            return _json_error(422, "Unprocessable Entity",
                               f"Program '{program.name}' is not active (state: {program.state})")

        # Validate beneficiary exists
        beneficiary = request.env["g2p.registrant"].sudo().browse(beneficiary_id)
        if not beneficiary.exists():
            return _json_error(404, "Not Found", f"Beneficiary with id={beneficiary_id} does not exist")

        # Check for duplicate enrollment
        existing = request.env["g2p.program_membership"].sudo().search([
            ("program_id", "=", program_id),
            ("partner_id", "=", beneficiary_id),
        ], limit=1)

        if existing:
            return _json_error(
                409, "Conflict",
                f"Beneficiary {beneficiary_id} is already enrolled in program '{program.name}'",
                {
                    "membership_id":  existing.id,
                    "current_state":  existing.state,
                    "enrolled_at":    str(existing.create_date) if existing.create_date else None,
                },
            )

        try:
            membership = request.env["g2p.program_membership"].sudo().create({
                "program_id": program_id,
                "partner_id": beneficiary_id,
                "state":      "enrolled",
            })
            _logger.info(
                "GovAid API: Enrolled beneficiary=%s in program='%s' (membership_id=%s)",
                beneficiary_id, program.name, membership.id,
            )
            return _json_response({
                "membership_id":  membership.id,
                "program_id":     program_id,
                "program_name":   program.name,
                "beneficiary_id": beneficiary_id,
                "beneficiary_name": beneficiary.name,
                "state":          membership.state,
                "enrolled_at":    str(membership.create_date) if membership.create_date else None,
            }, status=201)
        except Exception as e:
            _logger.error("GovAid API: enroll_beneficiary failed: %s", str(e), exc_info=True)
            return _json_error(500, "Internal Server Error", f"Enrollment failed: {str(e)}")
