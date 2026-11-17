from odoo import api, fields, models


class OtmLeadExportEnterCodeWizard(models.TransientModel):
    _name = 'otm.lead.export.enter.code.wizard'
    _description = 'Enter Lead Export Unlock Code'

    request_id = fields.Many2one(
        'otm.lead.export.request', string='Export Request', required=True,
        domain="[('user_id', '=', uid), ('state', '=', 'approved')]")
    code = fields.Char(string='6-digit code', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'request_id' in fields_list and not res.get('request_id'):
            req = self.env['otm.lead.export.request'].search([
                ('user_id', '=', self.env.user.id), ('state', '=', 'approved'),
            ], limit=1, order='id desc')
            if req:
                res['request_id'] = req.id
        return res

    def action_confirm(self):
        self.ensure_one()
        request = self.request_id
        if request.user_id.id != self.env.user.id:
            # Never raise here either — same non-raising discipline as a
            # wrong code, this is just a different failure to report.
            return self._notify('danger', 'Not your request',
                                 'This request does not belong to you.')
        ok, message = request.sudo().action_enter_code(self.code)
        return self._notify('success' if ok else 'danger',
                             'Unlocked' if ok else 'Not unlocked', message,
                             close=ok)

    def _notify(self, kind, title, message, close=False):
        params = {'title': title, 'message': message, 'sticky': False, 'type': kind}
        if close:
            # On a correct code: close this dialog after the toast so the
            # request form behind it (open since the request wizard's own
            # redirect) refreshes and shows the new unlocked_until — same
            # "don't leave the user stuck on just a toast" fix as the
            # request wizard. On a wrong/locked code, the dialog stays
            # open so they can try again (or see it's now locked).
            params['next'] = {'type': 'ir.actions.act_window_close'}
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': params,
        }
