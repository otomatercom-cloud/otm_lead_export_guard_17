from . import models
from . import wizard


def grant_staff_defaults(env):
    """Every internal user may request an export unlock ('Lead Export
    Allowed'). Used by the install hook and by the upgrade migration; an
    administrator can still switch a user off under Export Access."""
    grp = env.ref('otm_lead_export_guard.group_lead_export')
    Users = env['res.users'].with_context(active_test=False)
    staff = Users.search([('share', '=', False), ('groups_id', 'not in', grp.id)])
    if staff:
        staff.write({'groups_id': [(4, grp.id)]})
    # Approvers keep their dedicated group in sync with the Approvers list.
    env['otm.lead.export.approver']._sync_approver_group()


def grant_admin_bootstrap(env):
    """The first Lead Export Admin is the built-in admin user, so the
    module can be managed from day one. Only while nobody holds the group;
    afterwards membership is changed only by a Lead Export Admin."""
    grp = env.ref('otm_lead_export_guard.group_lead_export_admin')
    if not env['res.users'].with_context(active_test=False).search_count(
            [('groups_id', 'in', grp.id)]):
        admin = env.ref('base.user_admin', raise_if_not_found=False)
        if admin:
            admin.write({'groups_id': [(4, grp.id)]})


def post_init_hook(env):
    """Export is blocked for everyone without an approved, unexpired unlock;
    this only decides who gets the *button* and may *request* one."""
    allow = env.ref('base.group_allow_export', raise_if_not_found=False)
    if allow:
        user_grp = env.ref('base.group_user')
        if allow in user_grp.implied_ids:
            # Visibility of the Export button now comes from the module's
            # own group (which implies it), not from every internal user.
            user_grp.write({'implied_ids': [(3, allow.id)]})
    grant_staff_defaults(env)
    grant_admin_bootstrap(env)
    if allow:
        grp = env.ref('otm_lead_export_guard.group_lead_export')
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
