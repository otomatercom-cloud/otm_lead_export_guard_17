from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError

MODULE = 'otm_lead_export_guard'
STAFF = f'{MODULE}.group_lead_export'
APPROVER = f'{MODULE}.group_lead_export_approver'
ADMIN = f'{MODULE}.group_lead_export_admin'
GUARDED = (STAFF, APPROVER, ADMIN)
DENIED = _("Only a Lead Export Admin can change who may request, approve "
           "or administer lead exports.")


class ResUsers(models.Model):
    _inherit = 'res.users'

    otm_can_export_leads = fields.Boolean(
        string='Can export leads', compute='_compute_otm_can_export_leads',
        inverse='_inverse_otm_can_export_leads', search='_search_otm_can_export_leads')

    def _otm_export_group(self):
        return self.env.ref(STAFF)

    # ── who may change Lead Export roles ──────────────────────────────
    # Settings access (base.group_system) is NOT enough: some people need
    # Settings but must not control export approvals. Only a Lead Export
    # Admin may. Bootstrap: while nobody holds the group, a Settings user
    # may assign it so the module can never be locked out.
    @api.model
    def _otm_actor_may_manage_export_roles(self):
        user = self.env.user
        if user.id == SUPERUSER_ID:
            return True
        if user.has_group(ADMIN):
            return True
        grp = self.env.ref(ADMIN)
        nobody = not self.env['res.users'].sudo().search_count([('groups_id', 'in', grp.id)])
        return nobody and user.has_group('base.group_system')

    def _otm_guarded_ids(self):
        return {self.env.ref(x).id for x in GUARDED}

    @api.model
    def _otm_touches_groups(self, vals):
        return any(k == 'groups_id' or k.startswith(('in_group_', 'sel_groups_')) for k in vals)

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        if not self.env.su and any(self._otm_touches_groups(v) for v in vals_list):
            # staff group is a create-time default for everyone; the two
            # privileged groups are not.
            priv = {self.env.ref(APPROVER).id, self.env.ref(ADMIN).id}
            if any(set(u.groups_id.ids) & priv for u in users) \
                    and not self._otm_actor_may_manage_export_roles():
                raise AccessError(DENIED)
        return users

    def write(self, vals):
        if self.env.su:
            return super().write(vals)
        if 'otm_can_export_leads' in vals:
            if not self._otm_actor_may_manage_export_roles():
                raise AccessError(DENIED)
            # a Lead Export Admin needn't have Settings rights to switch
            # a user's export access on/off
            return self.sudo().write(vals)
        if not self._otm_touches_groups(vals):
            return super().write(vals)
        gids = self._otm_guarded_ids()
        # decide BEFORE writing: otherwise a user could grant themselves
        # Lead Export Admin and then pass the check as the new admin
        allowed = self._otm_actor_may_manage_export_roles()
        before = {u.id: set(u.groups_id.ids) & gids for u in self}
        res = super().write(vals)
        if not allowed:
            self.invalidate_recordset(['groups_id'])
            if any(set(u.groups_id.ids) & gids != before[u.id] for u in self):
                raise AccessError(DENIED)  # rolls the whole write back
        return res

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


class ResGroups(models.Model):
    _inherit = 'res.groups'

    def write(self, vals):
        # the Users tab of a group form bypasses res.users.write
        if 'users' in vals and not self.env.su:
            gids = {self.env.ref(x).id for x in GUARDED}
            if set(self.ids) & gids and not self.env['res.users']._otm_actor_may_manage_export_roles():
                raise AccessError(DENIED)
        return super().write(vals)
