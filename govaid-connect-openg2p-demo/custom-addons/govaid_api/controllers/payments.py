"""
GovAid API — Payments Endpoint
================================

Endpoint:
    GET /govaid/v1/payments/<beneficiaryId>

Retrieves payment/disbursement history for a specific beneficiary.
Sensitive bank details are NEVER returned in the response.
"""
import logging

from odoo import http
from odoo.http import request
from .main import govaid_api_auth, _json_response, _json_error

_logger = logging.getLogger(__name__)


class GovAidPaymentsController(http.Controller):

    @http.route(
        "/govaid/v1/payments/<int:beneficiary_id>",
        type="http",
        auth="none",
        methods=["GET"],
        csrf=False,
        cors="*",
        save_session=False,
    )
    @govaid_api_auth
    def get_payments(self, beneficiary_id, **kwargs):
        """
        Get payment disbursement history for a beneficiary.

        Path Parameters:
            beneficiary_id (int) — Odoo record ID of the beneficiary

        Query Parameters:
            limit  (int, default=50) — max records to return
            offset (int, default=0)  — pagination offset

        Returns:
            200 OK  — list of payment records (no sensitive bank data)
            404     — beneficiary not found
        """
        # Validate pagination params
        try:
            limit  = min(int(kwargs.get("limit", 50)), 200)
            offset = max(int(kwargs.get("offset", 0)), 0)
        except (ValueError, TypeError):
            return _json_error(400, "Bad Request", "limit and offset must be integers")

        # Validate beneficiary exists
        beneficiary = request.env["g2p.registrant"].sudo().browse(beneficiary_id)
        if not beneficiary.exists():
            return _json_error(404, "Not Found", f"Beneficiary {beneficiary_id} not found")

        payments_data = []

        try:
            # Try to query g2p.payment model (available if disbursement module is installed)
            payments = request.env["g2p.payment"].sudo().search(
                [("partner_id", "=", beneficiary_id)],
                order="payment_datetime desc",
                limit=limit,
                offset=offset,
            )
            total = request.env["g2p.payment"].sudo().search_count(
                [("partner_id", "=", beneficiary_id)]
            )

            for p in payments:
                payments_data.append({
                    "payment_id":      p.id,
                    "program_id":      p.program_id.id if p.program_id else None,
                    "program_name":    p.program_id.name if p.program_id else None,
                    "amount":          float(p.amount_issued) if p.amount_issued else 0.0,
                    "currency":        p.currency_id.name if p.currency_id else None,
                    "status":          p.state,
                    "payment_date":    str(p.payment_datetime) if p.payment_datetime else None,
                    # NEVER include: bank_account_id, account_number, iban, etc.
                })

        except KeyError:
            # g2p.payment model not available — return enrollment-based summary
            _logger.warning(
                "GovAid API: g2p.payment model not available — returning enrollment summary instead"
            )
            memberships = request.env["g2p.program_membership"].sudo().search([
                ("partner_id", "=", beneficiary_id),
            ])
            total = len(memberships)
            for m in memberships:
                payments_data.append({
                    "program_id":   m.program_id.id,
                    "program_name": m.program_id.name,
                    "state":        m.state,
                    "note":         "Payment disbursement module not installed",
                })

        _logger.info(
            "GovAid API: Payment query for beneficiary=%s returned %d records",
            beneficiary_id, len(payments_data),
        )

        return _json_response({
            "beneficiary_id":   beneficiary_id,
            "beneficiary_name": beneficiary.name,
            "total":            total if 'total' in dir() else len(payments_data),
            "count":            len(payments_data),
            "offset":           offset,
            "limit":            limit,
            "payments":         payments_data,
        })
