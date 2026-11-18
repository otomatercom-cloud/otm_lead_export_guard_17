from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """17.0.1.1.0 -> 17.0.1.2.0: every staff member may request an export
    unlock, and the Approvals menu is gated by a dedicated approver group
    kept in sync with the Approvers list."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.otm_lead_export_guard import grant_staff_defaults
    grant_staff_defaults(env)
