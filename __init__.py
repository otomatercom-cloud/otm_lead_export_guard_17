from . import models


def post_init_hook(env):
    """Make export an opt-in right: only 'Lead Export Allowed' users keep it."""
    allow = env.ref('base.group_allow_export', raise_if_not_found=False)
    grp = env.ref('otm_lead_export_guard.group_lead_export')
    if not allow:
        return
    user_grp = env.ref('base.group_user')
    if allow in user_grp.implied_ids:
        user_grp.write({'implied_ids': [(3, allow.id)]})
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    if admin:
        admin.write({'groups_id': [(4, grp.id)]})
    Users = env['res.users'].with_context(active_test=False)
    keep = Users.search([('groups_id', 'in', grp.id)])
    drop = Users.search([('groups_id', 'in', allow.id), ('id', 'not in', keep.ids)])
    if drop:
        drop.write({'groups_id': [(3, allow.id)]})


def uninstall_hook(env):
    allow = env.ref('base.group_allow_export', raise_if_not_found=False)
    user_grp = env.ref('base.group_user', raise_if_not_found=False)
    if allow and user_grp:
        user_grp.write({'implied_ids': [(4, allow.id)]})
        users = env['res.users'].with_context(active_test=False).search([('share', '=', False)])
        users.write({'groups_id': [(4, allow.id)]})
