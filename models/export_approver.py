from odoo import api, fields, models

APPROVER_GROUP = 'otm_lead_export_guard.group_lead_export_approver'


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

    # ── group sync ────────────────────────────────────────────────────
    # Lead Export > Approvals is gated by the "Lead Export Approver" group
    # (menu + ACL). That group is never assigned by hand: it mirrors this
    # admin-only list, so only an administrator decides who can approve.
    @api.model
    def _sync_approver_group(self, users=None):
        """Make group membership match the active rows of this table.
        `users` limits the work to specific users (after a change)."""
        grp = self.env.ref(APPROVER_GROUP, raise_if_not_found=False)
        if not grp:
            return
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        active_ids = set(self.sudo().search([('active', '=', True)]).user_id.ids)
        candidates = users if users is not None else (
            Users.search([('groups_id', 'in', grp.id)]) | Users.browse(active_ids))
        for user in candidates.sudo():
            should = user.id in active_ids
            has = grp in user.groups_id
            if should and not has:
                user.write({'groups_id': [(4, grp.id)]})
            elif has and not should:
                user.write({'groups_id': [(3, grp.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._sync_approver_group(records.user_id)
        return records

    def write(self, vals):
        before = self.user_id
        res = super().write(vals)
        if 'active' in vals or 'user_id' in vals:
            self._sync_approver_group(before | self.user_id)
        return res

    def unlink(self):
        users = self.user_id
        res = super().unlink()
        self._sync_approver_group(users)
        return res
