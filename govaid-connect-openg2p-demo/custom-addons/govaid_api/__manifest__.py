{
    'name': 'GovAid REST API',
    'version': '17.0.1.0.0',
    'category': 'Government / Social Protection',
    'summary': 'REST API controllers for GovAid — exposes beneficiary, program, eligibility, payment, and grievance endpoints behind WSO2 API Manager',
    'description': """
GovAid REST API Module
======================

This module exposes clean, versioned REST API endpoints for the GovAid platform.
All endpoints are designed to be called through WSO2 API Manager (OAuth2 gateway).

Authentication:
    - WSO2 validates Bearer tokens from external clients
    - WSO2 injects a shared X-GovAid-Api-Key header before forwarding to Odoo
    - Odoo controllers validate the API key — no session auth needed

Endpoints:
    GET  /govaid/v1/beneficiaries
    POST /govaid/v1/beneficiaries
    GET  /govaid/v1/beneficiaries/<id>
    POST /govaid/v1/programs/<programId>/enroll
    POST /govaid/v1/eligibility/check
    GET  /govaid/v1/payments/<beneficiaryId>
    POST /govaid/v1/grievances

Environment Variables:
    GOVAID_WSO2_API_KEY: Shared secret between WSO2 and Odoo (32-char hex string)
    """,
    'author': 'GovAid Team',
    'website': 'https://govaid.example.gov',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'g2p_registry_base',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
