import logging

from odoo import SUPERUSER_ID, api, fields, models

_logger = logging.getLogger(__name__)


class OtmLeadExportLog(models.Model):
    _name = 'otm.lead.export.log'
    _description = 'Lead Export Log'
    _order = 'id desc'

    user_id = fields.Many2one('res.users', string='User', readonly=True, index=True)
    date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    model = fields.Char(readonly=True)
    record_count = fields.Integer(string='Records', readonly=True)
    field_count = fields.Integer(string='Fields', readonly=True)
    # 'allowed'/'blocked' kept for backward compatibility with rows written
    # by the pre-unlock-feature version of this module; new rows use the
    # richer values added for export-unlock (spec.md US7).
    result = fields.Selection([
        ('allowed', 'Exported (legacy)'),
        ('blocked', 'Blocked (legacy)'),
        ('exported', 'Exported'),
        ('requested', 'Requested'),
        ('unlocked', 'Unlocked'),
        ('wrong_code', 'Wrong Code'),
        ('locked', 'Locked'),
        ('expired', 'Expired'),
    ], readonly=True, index=True)
    note = fields.Text(readonly=True)
    request_id = fields.Many2one('otm.lead.export.request', string='Export Request',
                                  readonly=True, index=True)

    @api.model
    def _log_isolated(self, vals):
        """Writes a log row on its own cursor, independent of the caller's
        transaction, so a row written right before a later raise/rollback
        still survives — see constitution.md "log write must survive a
        raised error". Never raises itself: a logging failure must never
        break the feature it's auditing."""
        try:
            with self.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env['otm.lead.export.log'].create(vals)
        except Exception:
            _logger.exception("Could not write lead export log: %s", vals)
