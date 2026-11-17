from odoo import api, fields, models


class OtmLeadExportApprover(models.Model):
    _name = 'otm.lead.export.approver'
    _description = 'Lead Export Approver (Director)'
    _order = 'id desc'
    _rec_name = 'name'

    user_id = fields.Many2one('res.users', string='Director', required=True,
                               ondelete='cascade')
    name = fields.Char(related='user_id.name', store=True, readonly=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('user_unique', 'unique(user_id)', 'This user is already an approver.'),
    ]

    def _grant_export_group(self):
        """Being on this list must be enough, on its own, for the user to
        reach the Lead Export app and Approvals — admin decides who that
        is (by adding them here, or via Export Access), never the user
        themselves. Only ADDS the group, never removes it when an
        approver is deactivated — taking export visibility away stays a
        deliberate Export Access action, not a side effect of this one."""
        grp = self.env.ref('otm_lead_export_guard.group_lead_export', raise_if_not_found=False)
        if not grp:
            return
        for approver in self.filtered('active'):
            if grp not in approver.user_id.groups_id:
                approver.user_id.sudo().write({'groups_id': [(4, grp.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._grant_export_group()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'active' in vals or 'user_id' in vals:
            self._grant_export_group()
        return res
