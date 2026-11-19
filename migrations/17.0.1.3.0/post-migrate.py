from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """17.0.1.2.0 -> 17.0.1.3.0: Approvers / Export Access / Export Log move
    from Settings (base.group_system) to the dedicated Lead Export Admin
    group. The built-in admin user becomes the first member."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.otm_lead_export_guard import grant_admin_bootstrap
    grant_admin_bootstrap(env)
    # <menuitem groups=...> on update only ADDS groups, it never removes the
    # old one, so strip Settings from this module's menus explicitly.
    system = env.ref('base.group_system')
    ids = env['ir.model.data'].search([
        ('module', '=', 'otm_lead_export_guard'), ('model', '=', 'ir.ui.menu')]).mapped('res_id')
    menus = env['ir.ui.menu'].browse(ids).exists()
    menus.write({'groups_id': [(3, system.id)]})
