# Constitution — Export Unlock feature

Applies to every change made under this spec, inside `otm_lead_export_guard`.
Extends (does not replace) the module's existing guard behaviour.

## Platform
- Odoo **17.0** only. No syntax, field, or API that requires 18/19.
- License `OPL-1`, author `Otomater`, model prefix `otm.`.
- Depends only on `base`, `web`, `custom_leads`. No hard dependency on
  `software_telegram` or any mail module — Telegram push is optional and
  must degrade to a safe no-op if the bridge isn't installed/configured.

## Security
- Never touch `ir.model.access.csv` rows, views, or security rules
  belonging to `custom_leads` or any other module. Every model this
  feature adds gets its own ACL row(s) in this module's own CSV.
- Real enforcement is server-side, in `export_data()`. Any UI affordance
  (button visibility, menu visibility) is convenience only and must never
  be the only thing standing between a user and an export.
- A 6-digit code is never kept in plaintext longer than the brief window
  between generation and the approver's one-time reveal (or natural
  expiry). It is never rendered in any view, log, or export reachable by
  the requester or by an admin browsing the UI — only the approver's
  one-time reveal dialog ever displays it. (This is an application-layer
  guarantee: someone with raw database access during that short window is
  a separate, out-of-scope threat — called out in plan.md's risk table
  rather than silently assumed away.)

## Reliability
- A log write (`otm.lead.export.log`) must survive a raised error in the
  same request — it runs on its own cursor/environment, exactly like the
  existing `_otm_log_export` already does.
- A failed-attempt counter write must survive even when the surrounding
  action ends in a non-raising "wrong code" response — see plan.md's note
  on why wrong-code handling must not `raise`.
- A failure to notify (Telegram, or anything else optional) must never
  block or roll back the underlying request/approval/unlock action.

## Process
- Every new Python file is checked with `python -m py_compile` and every
  new/changed XML file is checked with `xml.etree.ElementTree.parse`
  before delivery.
- Nothing here has been run against a live Odoo 17 server in this
  session — no database, no running `odoo-bin` is available here. That is
  stated plainly in the delivery notes rather than implied as "tested."
- If an assumption in spec.md/plan.md turns out to contradict the actual
  Odoo 17.0 source or the actual `custom_leads`/existing-guard code, the
  source code wins — say so explicitly and adapt, never guess silently.
  (One such contradiction was already found and corrected while planning
  this feature — see plan.md, "Corrected from the brief".)
