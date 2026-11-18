from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


class OtmLeadExportApprovalWizard(models.TransientModel):
    _name = 'otm.lead.export.approval.wizard'
    _description = 'Approve Pending Lead Export Requests'

    line_ids = fields.One2many(
        'otm.lead.export.approval.wizard.line', 'wizard_id', string='Pending Requests')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        self._check_is_approver()
        pending = self.env['otm.lead.export.request'].sudo().search([
            ('state', '=', 'sent'),
            ('user_id', '!=', self.env.user.id),
        ])
        res['line_ids'] = [(0, 0, {
            'request_id': r.id,
            'requester_id': r.user_id.id,
            'reason': r.reason,
            'minutes': r.minutes,
            'request_date': r.request_date,
        }) for r in pending]
        return res

    def _check_is_approver(self):
        is_approver = self.env['otm.lead.export.approver'].sudo().search_count([
            ('user_id', '=', self.env.user.id), ('active', '=', True),
        ])
        if not is_approver:
            raise AccessError(
                "You are not on the Lead Export Approvers list. Ask the "
                "administrator to add you under Lead Export > Approvers.")


class OtmLeadExportApprovalWizardLine(models.TransientModel):
    _name = 'otm.lead.export.approval.wizard.line'
    _description = 'Pending Request Line (Approval Wizard)'

    wizard_id = fields.Many2one('otm.lead.export.approval.wizard', ondelete='cascade')
    request_id = fields.Many2one('otm.lead.export.request', readonly=True)
    requester_id = fields.Many2one('res.users', string='Requester', readonly=True)
    reason = fields.Text(readonly=True)
    minutes = fields.Selection([
        ('5', '5 minutes'), ('10', '10 minutes'), ('15', '15 minutes'),
        ('20', '20 minutes'), ('30', '30 minutes'),
    ], readonly=True)
    request_date = fields.Datetime(readonly=True)

    def action_reveal(self):
        """Reveals the code exactly once, inline, to this approver's
        browser only — see plan.md 'Code delivery'. The code is never
        written back onto this wizard line or any stored field."""
        self.ensure_one()
        self.wizard_id._check_is_approver()
        request = self.request_id.sudo()
        try:
            code = request._approve_and_reveal(self.env.user)
        except UserError as exc:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'title': 'Could not reveal code', 'message': str(exc),
                           'sticky': False, 'type': 'danger'},
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': f'Code for {request.user_id.name}',
                'message': f'{code} — valid 10 minutes, shown once. Also emailed to '
                            f'{request.user_id.name} if they have an email on file and '
                            f'an outgoing mail server is configured — tell them directly '
                            f'too in case that mail does not arrive.',
                'sticky': True,
                'type': 'success',
            },
        }
