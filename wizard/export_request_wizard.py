from odoo import fields, models


class OtmLeadExportRequestWizard(models.TransientModel):
    _name = 'otm.lead.export.request.wizard'
    _description = 'Request a Lead Export Unlock'

    reason = fields.Text(required=True)
    minutes = fields.Selection([
        ('5', '5 minutes'), ('10', '10 minutes'), ('15', '15 minutes'),
        ('20', '20 minutes'), ('30', '30 minutes'),
    ], required=True, default='10')

    def action_submit(self):
        self.ensure_one()
        request = self.env['otm.lead.export.request'].create({
            'user_id': self.env.user.id,
            'reason': self.reason,
            'minutes': self.minutes,
        })
        request._log('requested', note='Request submitted')
        # Close this popup and land on the request's own form (statusbar +
        # the "Enter Code" button, which appears automatically once a
        # Director approves it) — rather than leaving the user on just a
        # toast with nothing to come back to. The toast shows first, then
        # the client follows 'next' to open the form.
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Export request sent',
                'message': 'A Director must approve and reveal a code before '
                            'you can export. "Enter Code" will appear here '
                            'once it is approved.',
                'sticky': False,
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': 'Export Request',
                    'res_model': 'otm.lead.export.request',
                    'res_id': request.id,
                    'view_mode': 'form',
                    'views': [(False, 'form')],
                    'target': 'current',
                },
            },
        }
