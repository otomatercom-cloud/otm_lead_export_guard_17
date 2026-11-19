# Run: odoo shell -d <test db> < tests/roles_odoo_shell.py  (commits data; TEST database only)
from odoo import fields
M='otm_lead_export_guard.'
Users=env['res.users'].with_context(no_reset_password=True)
res=[]
def chk(l,c,x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ')+l,x)
def denied(l,fn):
    try: fn(); chk(l,False,'(allowed!)')
    except Exception as e: chk(l,True,'['+type(e).__name__+']')
    env.cr.rollback()
old=Users.with_context(active_test=False).search([('login','like','r2_%')])
env['otm.lead.export.approver'].sudo().search([('user_id','in',old.ids)]).unlink(); old.unlink(); env.cr.commit()
sysg=env.ref('base.group_system'); la=env.ref(M+'group_lead_export_admin')
settings=Users.create({'name':'R2 Settings','login':'r2_settings','email':'a@x.com','groups_id':[(4,sysg.id),(4,env.ref('base.group_erp_manager').id),(4,env.ref('base.group_partner_manager').id)]})
ladmin=Users.create({'name':'R2 LeadAdmin','login':'r2_ladmin','email':'b@x.com','groups_id':[(4,la.id)]})
both=Users.create({'name':'R2 Both','login':'r2_both','email':'d@x.com','groups_id':[(4,la.id),(4,sysg.id),(4,env.ref('base.group_erp_manager').id),(4,env.ref('base.group_partner_manager').id)]})
staff=Users.create({'name':'R2 Staff','login':'r2_staff','email':'c@x.com'})
env.cr.commit()
chk('built-in admin is Lead Export Admin (bootstrap)', la in env.ref('base.user_admin').groups_id)
chk('Settings-only user is NOT lead admin', la not in settings.groups_id and settings.has_group('base.group_system'))
def menus(u):
    root=env.ref(M+'menu_lead_export_root')
    vis=env['ir.ui.menu'].with_user(u.id)._visible_menu_ids()
    kids=root.with_context(**{'ir.ui.menu.full_list':True}).child_id.sorted('sequence')
    return [m.name for m in kids if m.id in vis]
ms=menus(settings); ml=menus(ladmin)
print('  settings-only menus',ms); print('  lead-admin menus',ml)
chk('Settings-only: no Approvers/Export Access/Export Log/Approvals', not set(ms)&{'Approvers','Export Access','Export Log','Approvals'}, ms)
chk('Lead Admin (no Settings): Approvers/Export Access/Export Log', {'Approvers','Export Access','Export Log'}<=set(ml), ml)
es=env(user=settings.id); el=env(user=ladmin.id)
denied('Settings-only cannot add approver', lambda: es['otm.lead.export.approver'].create({'user_id':staff.id}))
denied('Settings-only cannot read Export Log', lambda: es['otm.lead.export.log'].search([]))
denied('Settings-only cannot toggle Export Access', lambda: setattr(es['res.users'].browse(staff.id),'otm_can_export_leads',False))
denied('Settings-only cannot tick approver group on a user form', lambda: es['res.users'].browse(staff.id).write({'groups_id':[(4,env.ref(M+'group_lead_export_approver').id)]}))
denied('Settings-only cannot make self Lead Admin', lambda: es['res.users'].browse(settings.id).write({'groups_id':[(4,la.id)]}))
denied('Settings-only cannot add via group form Users tab', lambda: es['res.groups'].browse(la.id).write({'users':[(4,settings.id)]}))
denied('Settings-only cannot create user with approver group', lambda: es['res.users'].create({'name':'X','login':'r2_x','groups_id':[(4,env.ref(M+'group_lead_export_approver').id)]}))
# Settings user can still do normal user admin
try:
    es['res.users'].browse(staff.id).write({'name':'R2 Staff renamed'}); chk('Settings-only can still edit users normally',True)
except Exception as e: chk('Settings-only can still edit users normally',False,repr(e)[:150])
env.cr.rollback()
try:
    n=es['res.users'].create({'name':'R2 New','login':'r2_new','email':'n@x.com'}); chk('Settings-only can still create users (gets staff group)', env.ref(M+'group_lead_export') in n.groups_id)
except Exception as e: chk('Settings-only can still create users',False,repr(e)[:200])
env.cr.rollback()
# Lead admin powers
try:
    el['otm.lead.export.approver'].create({'user_id':staff.id}); env.cr.commit(); staff.invalidate_recordset()
    chk('Lead Admin adds approver -> approver group synced', env.ref(M+'group_lead_export_approver') in staff.groups_id)
except Exception as e: chk('Lead Admin adds approver',False,repr(e)[:200]); env.cr.rollback()
try:
    el['res.users'].browse(staff.id).otm_can_export_leads=False; env.cr.commit(); staff.invalidate_recordset()
    chk('Lead Admin (no Settings) toggles Export Access off', env.ref(M+'group_lead_export') not in staff.groups_id)
    el['res.users'].browse(staff.id).otm_can_export_leads=True; env.cr.commit(); staff.invalidate_recordset()
    chk('...and on again', env.ref(M+'group_lead_export') in staff.groups_id)
except Exception as e: chk('Lead Admin toggles Export Access',False,repr(e)[:200]); env.cr.rollback()
try:
    n=len(el['otm.lead.export.log'].search([])); chk('Lead Admin reads Export Log',True,n)
except Exception as e: chk('Lead Admin reads Export Log',False,repr(e)[:150]); env.cr.rollback()
try:
    env(user=both.id)['res.users'].browse(settings.id).write({'groups_id':[(4,la.id)]}); env.cr.commit(); settings.invalidate_recordset()
    chk('Lead Admin who also has Settings can promote another Lead Admin', la in settings.groups_id)
except Exception as e: chk('Lead Admin can promote',False,repr(e)[:200]); env.cr.rollback()
# cleanup
us=Users.with_context(active_test=False).search([('login','like','r2_%')])
env['otm.lead.export.approver'].sudo().search([('user_id','in',us.ids)]).unlink()
env['otm.lead.export.log'].sudo().search([('user_id','in',us.ids)]).unlink()
env['otm.lead.export.request'].sudo().search([('user_id','in',us.ids)]).unlink()
us.unlink(); env.cr.commit()
print(f"\nRESULT {sum(res)}/{len(res)}")
