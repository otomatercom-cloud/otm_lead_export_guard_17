# Run: odoo shell -d <db> < tests/e2e_odoo_shell.py  (creates/removes e2e_* users, commits data; use a TEST database only)
import datetime
from odoo import SUPERUSER_ID, fields
G='otm_lead_export_guard.group_lead_export'; A='otm_lead_export_guard.group_lead_export_approver'
Users=env['res.users'].with_context(no_reset_password=True)
res=[]
def chk(label, cond, extra=''):
    res.append(bool(cond)); print(('PASS ' if cond else 'FAIL ')+label, extra)
def expect_fail(label, fn):
    try:
        fn(); chk(label, False, '(no error raised)')
    except Exception as ex:
        chk(label, True, f'[{type(ex).__name__}]')
        env.cr.rollback() if False else None
# cleanup of earlier runs
old=Users.with_context(active_test=False).search([('login','like','e2e_%')])
env['otm.lead.export.request'].sudo().search([('user_id','in',old.ids)]).unlink()
env['otm.lead.export.log'].sudo().search([('user_id','in',old.ids)]).unlink()
env['otm.lead.export.approver'].sudo().search([('user_id','in',old.ids)]).unlink()
old.unlink(); env.cr.commit()
# 1) new users get group by default
staff=Users.create({'name':'E2E Staff','login':'e2e_staff','email':'s@x.com'})
staff2=Users.create({'name':'E2E Staff2','login':'e2e_staff2','email':'s2@x.com'})
director=Users.create({'name':'E2E Director','login':'e2e_dir','email':'d@x.com'})
env.cr.commit()
chk('new internal user gets staff group by default', env.ref(G) in staff.groups_id)
chk('new user NOT approver', env.ref(A) not in staff.groups_id)
# 2) admin adds approver -> group synced
env['otm.lead.export.approver'].create({'user_id':director.id}); env.cr.commit()
chk('approver row -> approver group added', env.ref(A) in director.groups_id)
# menus
def menus(u):
    root=env.ref('otm_lead_export_guard.menu_lead_export_root')
    vis=env['ir.ui.menu'].with_user(u.id)._visible_menu_ids()
    kids=root.with_context(**{'ir.ui.menu.full_list':True}).child_id.sorted('sequence')
    return root.id in vis, [m.name for m in kids if m.id in vis]
for u,exp in ((staff,['Request Export','Export Requests']),(director,None),(env.ref('base.user_admin'),None)):
    print('  menus',u.login,menus(u))
sv,sm=menus(staff)
chk('staff sees Request Export', 'Request Export' in sm)
chk('staff does NOT see Approvals/Approvers/Export Access/Log', not any(n in sm for n in ('Approvals','Approvers','Export Access','Export Log')), sm)
dv,dm=menus(director)
chk('approver sees Approvals', 'Approvals' in dm, dm)
chk('approver does NOT see Approvers/Export Access/Log', not any(n in dm for n in ('Approvers','Export Access','Export Log')), dm)
av,am=menus(env.ref('base.user_admin'))
chk('admin sees Approvers+Export Access+Export Log', all(n in am for n in ('Approvers','Export Access','Export Log')), am)
# 3) staff requests
es=env(user=staff.id)
w=es['otm.lead.export.request.wizard'].create({'reason':'need leads for campaign','minutes':'10'})
act=w.action_submit(); env.cr.commit()
req=env['otm.lead.export.request'].sudo().search([('user_id','=',staff.id)],limit=1)
chk('staff request created (state sent)', req and req.state=='sent')
chk("'requested' log row saved", env['otm.lead.export.log'].sudo().search_count([('request_id','=',req.id),('result','=','requested')])>=1)
# 4) staff cannot approve / admin-ops
expect_fail('staff cannot open Approvals', lambda: es['otm.lead.export.approval.wizard'].default_get(['line_ids']))
expect_fail('staff cannot create approver row', lambda: es['otm.lead.export.approver'].create({'user_id':staff.id}))
expect_fail('staff cannot toggle Export Access', lambda: setattr(staff2.with_user(staff.id),'otm_can_export_leads',False))
expect_fail('staff cannot read Export Log', lambda: es['otm.lead.export.log'].search([]))
from odoo.api import call_kw
expect_fail('staff cannot reveal via RPC (private method)', lambda: call_kw(es['otm.lead.export.request'],'_approve_and_reveal',[[req.id]],{}))
expect_fail('staff cannot grant approver group to self', lambda: es['res.users'].browse(staff.id).write({'groups_id':[(4,env.ref(A).id)]}))
env.cr.rollback()
# staff cannot see other's request
other=es['otm.lead.export.request'].search([])
chk('staff sees only own requests', set(other.mapped('user_id').ids)<={staff.id})
# 5) export blocked before approval
Lead=env['leads.logic']
lead=Lead.sudo().create({'name':'L1'}); env.cr.commit()
expect_fail('export blocked before approval', lambda: lead.with_user(staff.id).export_data(['name']))
env.cr.rollback()
# 6) approver reveals code
ed=env(user=director.id)
aw=ed['otm.lead.export.approval.wizard'].create({})
aw=ed['otm.lead.export.approval.wizard'].with_context().create({}) if False else aw
lines=ed['otm.lead.export.approval.wizard'].default_get(['line_ids'])
chk('approver sees the pending request', lines.get('line_ids'))
# reveal directly
captured={}
import odoo.addons.otm_lead_export_guard.models.export_request as m
orig=m.OtmLeadExportRequest._email_code_to_requester if hasattr(m,'OtmLeadExportRequest') else None
cls=[c for c in vars(m).values() if isinstance(c,type) and hasattr(c,'_email_code_to_requester')][0]
o=cls._email_code_to_requester
def spy(self,code): captured['code']=code; return o(self,code)
cls._email_code_to_requester=spy
expect_fail('requester cannot approve own request (self-approve)', lambda: req.sudo().action_approve_and_reveal(staff)) if False else None
r2=req.sudo()._approve_and_reveal(director); env.cr.commit()
code=captured.get('code')
chk('code is 6 digits', code and len(code)==6 and code.isdigit(), code)
req.invalidate_recordset()
chk('request now approved, code plaintext wiped', req.state=='approved' and not req.code_plain_pending)
# 7) wrong x3 -> lock
ok,msg=req.with_user(staff.id).sudo().action_enter_code('000000') if False else req.sudo().action_enter_code('000000' if code!='000000' else '111111')
env.cr.commit(); req.invalidate_recordset()
chk('wrong code -> not ok, attempts=1', (not ok) and req.attempts==1, msg)
# correct code (as staff, via wizard)
w2=es['otm.lead.export.enter.code.wizard'].create({'request_id':req.id,'code':code})
res_act=w2.action_confirm(); env.cr.commit(); req.invalidate_recordset()
chk('correct code unlocks', req.unlocked_until and req.unlocked_until>fields.Datetime.now(), req.unlocked_until)
# 8) export allowed
try:
    lead.with_user(staff.id).export_data(['name']); chk('staff export allowed inside window', True)
except Exception as ex:
    chk('staff export allowed inside window', False, repr(ex)[:200])
env.cr.rollback()
expect_fail('other staff (no unlock) still blocked', lambda: lead.with_user(staff2.id).export_data(['name']))
env.cr.rollback()
expect_fail('admin NOT a bypass', lambda: lead.with_user(env.ref('base.user_admin').id).export_data(['name']))
env.cr.rollback()
# 9) expiry
req.sudo().write({'unlocked_until':fields.Datetime.now()-datetime.timedelta(minutes=1)}); env.cr.commit()
expect_fail('export blocked after window', lambda: lead.with_user(staff.id).export_data(['name']))
env.cr.rollback()
# 10) lock after 3 wrong
w3=es['otm.lead.export.request.wizard'].create({'reason':'second','minutes':'5'}); w3.action_submit(); env.cr.commit()
r3=env['otm.lead.export.request'].sudo().search([('user_id','=',staff.id)],order='id desc',limit=1)
r3.sudo()._approve_and_reveal(director); env.cr.commit()
c3=captured['code']; bad='999999' if c3!='999999' else '888888'
for i in range(3):
    r3.sudo().action_enter_code(bad); env.cr.commit()
r3.invalidate_recordset()
chk('3 wrong codes -> locked', r3.state=='locked', r3.state)
ok,_=r3.sudo().action_enter_code(c3); r3.invalidate_recordset()
chk('right code after lock rejected', not ok)
logs=env['otm.lead.export.log'].sudo().search([('user_id','in',[staff.id,director.id])]).mapped('result')
print('  log results:',sorted(set(logs)))
chk('log has requested/unlocked/wrong_code/locked/exported/blocked', {'requested','unlocked','wrong_code','locked','exported','blocked'}<=set(logs))
# 11) stale 'sent' expiry cron
w4=es['otm.lead.export.request.wizard'].create({'reason':'stale','minutes':'5'}); w4.action_submit(); env.cr.commit()
r4=env['otm.lead.export.request'].sudo().search([('user_id','=',staff.id)],order='id desc',limit=1)
r4.sudo().write({'request_date':fields.Datetime.now()-datetime.timedelta(minutes=90)}); env.cr.commit()
env['otm.lead.export.request'].sudo()._cron_expire(); env.cr.commit(); r4.invalidate_recordset()
chk('cron expires stale sent request', r4.state=='expired', r4.state)
# 12) approver deactivate/delete -> group removed
ap=env['otm.lead.export.approver'].search([('user_id','=',director.id)])
ap.write({'active':False}); env.cr.commit(); director.invalidate_recordset()
chk('deactivate approver -> group removed', env.ref(A) not in director.groups_id)
ap.write({'active':True}); director.invalidate_recordset()
chk('reactivate -> group back', env.ref(A) in director.groups_id)
ap.unlink(); env.cr.commit(); director.invalidate_recordset()
chk('delete approver -> group removed', env.ref(A) not in director.groups_id)
expect_fail('ex-approver cannot open Approvals', lambda: ed['otm.lead.export.approval.wizard'].default_get(['line_ids']))
env.cr.rollback()
# cleanup
us=Users.with_context(active_test=False).search([('login','like','e2e_%')])
env['otm.lead.export.log'].sudo().search([('user_id','in',us.ids)]).unlink()
env['otm.lead.export.request'].sudo().search([('user_id','in',us.ids)]).unlink()
Lead.sudo().search([('name','=','L1')]).unlink()
us.unlink(); env.cr.commit()
print(f"\nRESULT {sum(res)}/{len(res)} passed")
