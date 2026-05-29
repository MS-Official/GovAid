"""
GovAid API — Eligibility Check Endpoint
=========================================

Endpoint:
    POST /govaid/v1/eligibility/check

Checks whether a beneficiary is eligible for one specific program
or summarizes eligibility across all active programs.
"""
import logging

from odoo import http
from odoo.http import request
from .main import govaid_api_auth, _json_response, _json_error, _parse_json_body

_logger = logging.getLogger(__name__)


class GovAidEligibilityController(http.Controller):

    @http.route(
        "/govaid/v1/eligibility/check",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        cors="*",
        save_session=False,
    )
    @govaid_api_auth
    def check_eligibility(self, **kwargs):
        """
        Check program eligibility for a beneficiary.

        Request Body (JSON):
            beneficiary_id (int, required) — Odoo record ID of the beneficiary
            program_id     (int, optional) — check for a specific program only

        Returns:
            200 OK — eligibility assessment for each program
        """
        body, err = _parse_json_body()
        if err:
            return err

        beneficiary_id = body.get("beneficiary_id")
        program_id     = body.get("program_id")

        if not beneficiary_id:
            return _json_error(400, "Bad Request", "beneficiary_id is required")

        # Validate beneficiary
        beneficiary = request.env["g2p.registrant"].sudo().browse(beneficiary_id)
        if not beneficiary.exists():
            return _json_error(404, "Not Found", f"Beneficiary {beneficiary_id} not found")

        # Fetch programs to check
        program_domain = [("state", "=", "active")]
        if program_id:
            program_domain.append(("id", "=", program_id))

        programs = request.env["g2p.program"].sudo().search(program_domain)

        if program_id and not programs:
            return _json_error(404, "Not Found", f"Active program with id={program_id} not found")

        # Eligibility assessment
        results = []
        for prog in programs:
            # Check existing enrollment
            existing_membership = request.env["g2p.program_membership"].sudo().search([
                ("program_id", "=", prog.id),
                ("partner_id", "=", beneficiary_id),
            ], limit=1)

            enrolled       = bool(existing_membership)
            enrollment_state = existing_membership.state if enrolled else None

            # Basic eligibility rule: not already enrolled
            # TODO: Extend with age criteria, income criteria, geographic criteria, etc.
            eligible = not enrolled
            reasons  = []

            if enrolled:
                reasons.append(f"Already enrolled (state: {enrollment_state})")

            results.append({
                "program_id":         prog.id,
                "program_name":       prog.name,
                "eligible":           eligible,
                "already_enrolled":   enrolled,
                "enrollment_state":   enrollment_state,
                "ineligibility_reasons": reasons if not eligible else [],
            })

        _logger.info(
            "GovAid API: Eligibility check for beneficiary=%s across %d programs",
            beneficiary_id, len(programs),
        )

        return _json_response({
            "beneficiary_id":   beneficiary_id,
            "beneficiary_name": beneficiary.name,
            "total_programs":   len(programs),
            "eligible_count":   sum(1 for r in results if r["eligible"]),
            "eligibility":      results,
        })
