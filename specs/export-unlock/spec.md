# Spec — Export Unlock

## Problem
`otm_lead_export_guard` currently blocks lead export for everyone except
members of "Lead Export Allowed" — a flat, permanent yes/no. The business
needs a controlled, audited, **temporary** exception: a user who normally
cannot export can be let through for a short window, only after a Director
approves and reveals a one-time code, with every step logged.

## User stories & acceptance criteria

**US1 — Group grants visibility, not access.**
Given a user is added to "Lead Export Allowed", when they open a Leads
list, then the Export button/menu is visible to them — but exporting
without a valid unlock still fails server-side with the lock message.

**US2 — Request export.**
Given a user in the group wants to export, when they open *Lead Export ▸
Request Export* and submit a reason (required) and a window (5/10/15/20/30
minutes, max 30), then a request is created in state `sent` and logged as
`requested`.

**US3 — Approver reveals a code.**
Given a pending (`sent`) request, when an Approver (a Director on the
Approvers list) opens *Lead Export ▸ Approvals*, then they see pending
requests from **other** users only (never their own — a user who is both
requester and approver cannot approve themselves) and can reveal a 6-digit
code exactly once; the request moves to `approved` and the reveal is
logged.

**US4 — Enter the code.**
Given an `approved` request with a revealed code, when the requester
enters it within 10 minutes, then: correct code → `unlocked_until` is set
to now + the requested minutes, logged `unlocked`; wrong code → attempt
counter increments and is logged `wrong_code`, without rolling back the
counter; 3rd wrong attempt → state becomes `locked`, logged `locked`, no
further attempts accepted; a new request from the same user automatically
expires (`expired`) any of their own still-open (`sent`/`approved`)
requests.

**US5 — Time-boxed export.**
Given `unlocked_until` is in the future, when that user exports, then it
succeeds and is logged `exported`. Given `unlocked_until` has passed (even
though the Export button is still visible), when they export, then it is
blocked and logged `blocked` — group membership alone is never enough.

**US6 — Admin is not a bypass.**
Given a user with admin/`base.group_system` access but no valid unlock,
when they try to export, then they are blocked exactly like any other
user. Only the literal superuser (`uid == 1`) bypasses this. Import is
completely unaffected — nothing here touches import in any way.

**US7 — Full audit trail.**
Given any step above happens, then a row exists in the Export Log with
user, record count, field count, a note, and one of: `requested`,
`unlocked`, `wrong_code`, `locked`, `expired`, `exported`, `blocked`.

## Out of scope
- Per-export record/row count limits.
- File watermarking of exported data.
- Wiring to the real `software_telegram` API (see Open Questions — a safe
  stub hook point is built, not a working integration).

## Open questions / assumptions
Flagging these as assumptions per your instruction, rather than blocking
on them — correct me if any is wrong and I'll adjust.

1. **"Sent" (pending-approval) request expiry.** The brief gives the code
   a 10-minute validity after approval, but doesn't say how long an
   un-approved `sent` request waits before the minute-cron expires it on
   its own (independent of same-user supersession, which *is* specified).
   **Assumption: 60 minutes.** Easy to change — it's one constant in
   `models/export_request.py`.
2. **Telegram integration.** `software_telegram`'s actual model/method
   names weren't provided this session (no code for that module was
   attached — only a one-line description exists in project memory). I
   built the notify call as an isolated, try/except-wrapped stub behind a
   settings toggle (off by default) that currently **does nothing** even
   when turned on. Wiring it to the real bridge is a follow-up once that
   module's API is shared — flagged again in plan.md and the test
   checklist so it isn't mistaken for "done."
3. **Approver visibility mechanism.** The brief says approvers see other
   users' pending requests "via the Approvals action using sudo inside
   methods" rather than via `ir.rule`. I implemented "Approvals" as a
   wizard (not a direct list view on the real model) whose `default_get`
   and reveal action explicitly check "is this user an active approver"
   and then read/write with `sudo()`. This keeps the base `ir.rule` dead
   simple (own requests only, or everything for `base.group_system`) and
   avoids embedding search subqueries inside a rule's `domain_force`
   string, which is fragile. Detail in plan.md.
4. **"Never visible to the requester or to admin" (the code).** Read as
   an application-layer guarantee (no view/field ever renders it to them)
   rather than a claim that it's cryptographically hidden from someone
   with raw database access during the few seconds/minutes it's pending
   reveal — that's a different, out-of-scope threat model for a plain
   internal tool with no secrets infrastructure. Stated plainly in
   constitution.md and plan.md's risk table rather than overclaimed.
5. **Approver eligibility vs. existing `custom_leads` groups.** The brief
   describes Approvers as their own list ("Director list"), not reusing
   `custom_leads.group_lead_manager` or similar. Built as a standalone
   `otm.lead.export.approver` table exactly as specified — a Director
   doesn't need to already be a Lead-module Manager to approve. This also
   drove a menu fix caught in the analyze pass: the *Lead Export* menu is
   now top-level rather than nested under Settings, specifically so a
   Director with no admin rights can still reach *Approvals* — see
   plan.md's "Menus" section.
6. **Scope change: email now in use.** The original brief explicitly
   excluded email as the code's delivery channel ("no outgoing mail
   server"). The user later asked, after real testing, for the code to
   also reach the requester by mail "if they can't access Odoo" —
   reasonable, since the requester always has to receive this exact
   plaintext through some side channel before they can type it back in;
   this just automates that unavoidable hand-off. Implemented as
   `OtmLeadExportRequest._email_code_to_requester()` using Odoo's own
   `mail.mail` (no external bridge needed, unlike Telegram) — fired
   right after the approver reveals the code, wrapped in try/except so
   a missing/misconfigured outgoing mail server never blocks the reveal
   itself. Requires a working outgoing mail server under Settings >
   Technical > Email to actually deliver; the approver is still told
   the code directly too, as a fallback.
7. **Log `result` value for the approval/reveal step.** US7's result
   vocabulary (`requested`/`unlocked`/`wrong_code`/`locked`/`expired`/
   `exported`/`blocked`) has no dedicated value for "a Director revealed
   the code." Rather than add an 8th value outside what was specified,
   the reveal event is logged as `requested` too, with the `note` field
   ("Code revealed by <approver>") as the only way to tell the two
   `requested` rows for one request apart. Easy to change to a dedicated
   value if that's not what you want.
8. **Role model (17.0.1.2.0 redesign).** Original build gated *Request
   Export* behind `group_lead_export`, which an admin had to tick per user,
   and showed *Approvals* to everyone in that group. Real-server test
   showed plain staff could not request at all, and any group member could
   open Approvals. Now:
   - STAFF = `group_lead_export` ("Lead Export Allowed"), granted to every
     internal user by default (install hook, upgrade migration,
     `base.default_user` for new users). Sees Request Export + own
     Export Requests. Admin can still switch an individual off in Export
     Access. Membership never allows export on its own; the server guard
     still needs an approved, unexpired unlock.
   - APPROVER = `group_lead_export_approver`, never assigned by hand: it
     mirrors the admin-only Approvers list (create / deactivate / delete
     all sync). Sees Approvals. Cannot see Approvers / Export Access / Log.
   - ADMIN (`base.group_system`) = Approvers, Export Access, Export Log.
     Still no export bypass.
   Alternative if "only admin-enabled staff may request" is wanted: drop
   `data/export_defaults.xml`, the migration and `grant_staff_defaults`.
