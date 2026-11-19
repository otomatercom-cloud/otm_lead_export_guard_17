# Tasks — Export Unlock

Ordered, each checkable, each tagged with the user story it serves and
the file it touches.

## Models
- [x] T1 (US3,US7) `models/export_approver.py` — `otm.lead.export.approver`
- [x] T2 (US2,US4,US5,US7) `models/export_request.py` — `otm.lead.export.request`
      + HMAC helpers + `_cron_expire()` + supersession-on-new-request
- [x] T3 (US7) `models/export_log.py` — extend `result` selection + add
      `note`, `request_id` fields, plus the shared `_log_isolated()` helper
- [x] T4 (US1,US5,US6) `models/leads_export.py` — rewrite
      `_user_can_export`/`_check_can_export`/`export_data` for the new gate
- [x] T5 (all) `models/__init__.py` — register new model files
- [x] T6 — `models/res_config_settings.py` — Telegram-notify toggle
      (`ir.config_parameter`-backed)

## Wizards
- [x] T7 (US2) `wizard/export_request_wizard.py`
- [x] T8 (US3) `wizard/export_approval_wizard.py` — sudo-scoped list +
      one-time reveal
- [x] T9 (US4) `wizard/export_enter_code_wizard.py` — isolated-cursor
      wrong-code handling, no `raise`
- [x] T10 — `wizard/__init__.py`, `__init__.py` registers `wizard` package

## Data / Hooks
- [x] T11 (US5) `data/export_unlock_cron.xml` — 1-minute expiry cron
- [x] T12 (US1,US6) `__init__.py` — confirm existing hooks already match
      the brief (no change needed, documented in plan.md)

## Security
- [x] T13 (all) `security/ir.model.access.csv` — rows for every new model
      + every wizard
- [x] T14 (US4,US7,US6) `security/security.xml` — `ir.rule` on
      `otm.lead.export.request` (own-vs-admin domain, verbatim from brief)

## Views / Menus
- [x] T15 (US2) `views/export_request_wizard_views.xml`
- [x] T16 (US3) `views/export_approval_wizard_views.xml`
- [x] T17 (US4) `views/export_enter_code_wizard_views.xml`
- [x] T18 (US7) `views/export_guard_views.xml` — extend: Export Requests
      list/form, Approvers list/form, Export Log view gets `note`/`result`
      columns, new menu entries (Request Export, Export Requests,
      Approvals, Approvers); `menu_lead_export_root` groups extended to
      include `group_lead_export` alongside `base.group_system`
- [x] T19 (US6) `views/res_config_settings_views.xml` — Telegram toggle
      on Settings

## Manifest
- [x] T20 — `__manifest__.py` — version bump `17.0.1.1.0`, new data files
      listed (cron before the wizard views before `export_guard_views.xml`,
      so the `%(action_export_enter_code_wizard)d` button reference
      resolves), summary updated

## Validate & deliver
- [x] T21 — `python -m py_compile` every `.py` file — all pass
- [x] T22 — `xml.etree.ElementTree.parse` every `.xml` file (7 files) — all pass
- [x] T23 — analyze pass: diff implementation against spec.md/constitution.md.
      Found and fixed one real gap (menu nested under admin-only
      `base.menu_administration` would have hidden Approvals from
      non-admin Approvers — now a bare top-level menu) and documented one
      naming decision (reveal event logged as `requested` + note, no 8th
      result value invented). Both written up in plan.md/spec.md.
- [x] T24 — zip, test checklist, deploy steps, deliver
- [x] T25 — role redesign: staff default group, approver group synced from Approvers list, per-role menus, request ir.rule, migration 17.0.1.2.0
- [x] T26 — real Odoo 17 + Postgres 16 rig: fresh install, `-u` upgrade from 1.1.0, e2e matrix (menus per role, request, approve, wrong x3 lock, unlock window, expiry, cron, approver sync) — 35/35 pass
- [x] T27 — Lead Export Admin group, role-change guard, 17.0.1.3.0 migration (strips Settings from menus), 18/18 role checks + 35/35 flow checks on fresh install and upgrade
- [x] T28 — real-browser (Playwright) checks: Approvals dialog, Reveal Code, list refresh, requester Enter Code -> Unlocked; fixes: row-click popup (no_open), "Please click on the save button first" (wizard created+saved before showing, server action), request display name
