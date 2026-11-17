import logging

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)
GROUP = 'otm_lead_export_guard.group_lead_export'

LOCK_MESSAGE = _(
    "Lead export is locked. Open Lead Export > Request Export and enter "
    "the Director's approval code.")


class LeadsLogicExportGuard(models.Model):
    _inherit = 'leads.logic'

    @api.model
    def _user_can_export(self):
        """US1/US5/US6: group membership only grants visibility of the
        Export button — the actual gate is a currently-unlocked request.
        Only the literal superuser bypasses this; base.group_system does
        NOT (US6 — admin is not a bypass)."""
        user = self.env.user
        if user.id == SUPERUSER_ID:
            return True
        if not user.has_group(GROUP):
            return False
        req = self.env['otm.lead.export.request'].sudo().search([
            ('user_id', '=', user.id),
            ('unlocked_until', '>', fields.Datetime.now()),
        ], limit=1, order='unlocked_until desc')
        return bool(req)

    def _matched_request_note(self):
        """Best-effort note naming which unlocked request allowed this
        export, for the audit row. Returns '' if none (blocked case)."""
        user = self.env.user
        req = self.env['otm.lead.export.request'].sudo().search([
            ('user_id', '=', user.id),
            ('unlocked_until', '>', fields.Datetime.now()),
        ], limit=1, order='unlocked_until desc')
        return f'Matched request #{req.id}' if req else ''

    def _check_can_export(self):
        if not self._user_can_export():
            self._otm_log_export(False, 0)
            raise AccessError(LOCK_MESSAGE)
        return True

    def _otm_log_export(self, allowed, nfields):
        note = self._matched_request_note() if allowed else ''
        self.env['otm.lead.export.log'].sudo()._log_isolated({
            'user_id': self.env.uid,
            'model': self._name,
            'record_count': len(self),
            'field_count': nfields,
            'result': 'exported' if allowed else 'blocked',
            'note': note,
        })

    def export_data(self, fields_to_export):
        allowed = self._user_can_export()
        self._otm_log_export(allowed, len(fields_to_export or []))
        if not allowed:
            raise AccessError(LOCK_MESSAGE)
        return super().export_data(fields_to_export)
