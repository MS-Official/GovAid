"""
GovAid API — Configuration Settings
======================================
Adds GovAid API settings to Odoo's standard Settings page.
Allows administrators to configure the WSO2 API key through the UI
as an alternative to environment variables.
"""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    govaid_wso2_api_key = fields.Char(
        string="WSO2 API Key (Shared Secret)",
        config_parameter="govaid.wso2_api_key",
        help=(
            "The shared secret key injected by WSO2 API Manager via the "
            "X-GovAid-Api-Key header. Must match the value in the WSO2 "
            "mediation sequence. Generate with: openssl rand -hex 32"
        ),
    )

    govaid_api_rate_limit = fields.Integer(
        string="API Rate Limit (requests/minute)",
        config_parameter="govaid.api_rate_limit",
        default=500,
        help="Maximum number of API requests per minute (informational, enforced by WSO2)",
    )
