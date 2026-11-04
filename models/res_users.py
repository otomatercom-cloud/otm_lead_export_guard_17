from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    otm_can_export_leads = fields.Boolean(
        string='Can export leads', compute='_compute_otm_can_export_leads',
        inverse='_inverse_otm_can_export_leads', search='_search_otm_can_export_leads')

    def _otm_export_group(self):
        return self.env.ref('otm_lead_export_guard.group_lead_export')

    # Odoo 17.0: the res.users groups field is `groups_id` (Many2many to
    # res.groups). The rename to `group_ids` happened in a later series —
    # every reference below uses the 17.0 field name.
    @api.depends('groups_id')
    def _compute_otm_can_export_leads(self):
        grp = self._otm_export_group()
        for user in self:
            user.otm_can_export_leads = grp in user.groups_id

    def _inverse_otm_can_export_leads(self):
        grp = self._otm_export_group()
        for user in self:
            user.groups_id = [(4 if user.otm_can_export_leads else 3, grp.id)]

    def _search_otm_can_export_leads(self, operator, value):
        grp = self._otm_export_group()
        positive = (operator == '=') == bool(value)
        return [('groups_id', 'in' if positive else 'not in', grp.ids)]
