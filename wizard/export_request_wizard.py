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
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Export request sent',
                'message': 'A Director must approve and reveal a code before '
                            'you can export. Open Export Requests to track it, '
                            'then use Enter Code once it is approved.',
                'sticky': False,
                'type': 'success',
            },
        }
