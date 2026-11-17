# Plan — Export Unlock

## Corrected from the brief
The brief's Odoo 17 specifics section says hooks use signature
`(cr, registry)` with `env = api.Environment(cr, SUPERUSER_ID, {})`. I
checked this against the actual Odoo 17.0 source
(`odoo/modules/loading.py`, both the `post_init_hook` call site and the
`uninstall_hook` call site) rather than assume: in 17.0 both are called
as `getattr(py_module, hook_name)(env)` — **a single `env` argument**,
not `(cr, registry)`. The two-argument form was removed well before 17.0.
Using `(cr, registry)` here would raise `TypeError: missing 1 required
positional argument: 'registry'` the moment the module installs. The
existing guard's `__init__.py` already (correctly) uses the single-`env`
form — kept as-is, just extended with new logic below.

## Models

**`otm.lead.export.approver`** (new, `models/export_approver.py`)
`name` (related to `user_id.name`, stored, for list readability),
`user_id` (Many2one res.users, required), `active` (Boolean, default
True). SQL unique constraint on `user_id` — no duplicate approver rows.

**`otm.lead.export.request`** (new, `models/export_request.py`)
`user_id` (Many2one res.users, requester, default self, readonly),
`reason` (Text, required), `minutes` (Selection
5/10/15/20/30, required), `state` (Selection
sent/approved/expired/locked, default `sent`), `request_date` (Datetime,
default now), `code_hash` (Char) — HMAC digest, never the raw code,
`code_plain_pending` (Char) — see "Code delivery" below; wiped on reveal
and on expiry; excluded from every list/form view and every ACL except
the approver wizard's own sudo-scoped read, `code_expiry` (Datetime) —
10 minutes from approval, `attempts` (Integer, default 0), `locked_at`
NOT added (state=`locked` + log row already carries the "when"),
`unlocked_until` (Datetime) — the actual gate used by `export_data()`,
`approver_id` (Many2one res.users, who approved — addition beyond the
brief's bare field list, for audit/display; harmless and clearly useful).

**`otm.lead.export.log`** (existing, extended in place)
`result` Selection gets 5 new values appended —
`requested`/`unlocked`/`wrong_code`/`locked`/`expired` — alongside the
existing `allowed`/`blocked` (kept for backward compatibility with any
rows already written by the current guard). New `note` Text field for
free-form context (reason text, which approver, which request id).
New `request_id` Many2one (`otm.lead.export.request`, optional) so a
log row can be traced back to its request.

**Wizards** (`wizard/`, all TransientModel)
- `otm.lead.export.request.wizard` — reason + minutes, `action_submit()`
  creates the real `otm.lead.export.request` row (and expires the user's
  own previous open requests first).
- `otm.lead.export.approval.wizard` — opened from *Approvals*; on
  `default_get` it sudo-loads pending requests from **other** users only
  and blocks non-approvers outright; a per-line `action_reveal(request_id)`
  server method generates the code (if not already generated),
  HMAC-hashes it, stores the hash, sets `code_expiry`, stores the
  plaintext in `code_plain_pending` just long enough to hand back in the
  response, then **immediately wipes `code_plain_pending`** in the same
  write — the code is in the database unencrypted for roughly the
  duration of one ORM `write()` call, not for the full 10-minute window.
  The dialog shown to the approver is the only time anyone sees it.
- `otm.lead.export.enter.code.wizard` — opened from *Request Export* (or
  from the request's own record) once a request is `approved`; takes the
  6-digit input, compares via `hmac.compare_digest` against
  `code_hash`, and branches exactly as in "Wrong-code handling" below.

## Code
`hashlib.hmac`, key = `ir.config_parameter.sudo().get_param('database.secret')`
(Odoo's own per-database signing secret — already used internally by
Odoo itself for other signed tokens, so it's guaranteed present and
unique per install), message = `f"{request.id}:{code}"`,
`hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()`
stored as `code_hash`. Comparison always via `hmac.compare_digest`
(constant-time), never `==`.

## Code delivery (no mail, no hard Telegram dependency)
1. Approver opens *Lead Export ▸ Approvals* → wizard lists other users'
   `sent` requests (sudo-loaded, approver-only).
2. Clicking **Reveal Code** on a line: generates a random 6-digit code
   (`random.SystemRandom().randint(100000, 999999)` — a CSPRNG source,
   not the default `random` module), hashes it, writes `code_hash` +
   `code_expiry` + `state='approved'` + `approver_id`, and returns the
   plaintext code **once**, inline, in an `ir.actions.client` /
   `display_notification` (sticky) shown only to that approver's browser
   session. The plaintext is cleared from the database record in the
   same write — see constitution.md for exactly what guarantee this
   does and doesn't give.
3. Optional Telegram push: `_notify_telegram_stub(request)` on the
   request model, called right after step 2, wrapped in a bare
   `try/except Exception` that only logs a warning. Gated by a
   `res.config.settings` toggle (`otm_export_notify_telegram`, off by
   default). **Currently a no-op even when enabled** — see spec.md Open
   Question 2. No `software_telegram` entry in `depends`.

## Enforcement
Confirmed by grepping the full `custom_leads` zip: there is **no**
separate "Export Selected (All Fields)" controller or JS code path —
that label is Odoo's own native list-view export dialog (Export All /
Export Selected / "I want to update this spreadsheet"), and every one of
those options calls the server-side ORM method `export_data()` on the
recordset, with no alternate route. `custom_leads/models/leads.py`
*already* overrides `export_data()` on `leads.logic` (logs to its own
`lead.export.history` + posts a chatter note, then calls `super()`).
Since `otm_lead_export_guard` depends on `custom_leads`, Odoo's module
load order puts the guard's override **outermost** in the MRO: guard's
`export_data()` runs first (permission check + our own log), its
`super()` call reaches `custom_leads`'s override (its own unrelated
audit log + chatter note), whose `super()` finally reaches Odoo core.
No conflict, no change needed to `custom_leads`, nothing touched there.

`_user_can_export()` becomes:
```python
user = self.env.user
if user.id == SUPERUSER_ID:
    return True
if not user.has_group(GROUP):
    return False
req = self.env['otm.lead.export.request'].sudo().search([
    ('user_id', '=', user.id),
    ('unlocked_until', '>', fields.Datetime.now()),
], limit=1, order='unlocked_until desc')
return bool(req)
```
Message on failure (unchanged text, still accurate): *"Lead export is
locked. Open Lead Export > Request Export and enter the Director's
approval code."* `export_data()` logs `exported` on success / `blocked`
on failure instead of the old bare `allowed`/`blocked`, and includes a
`note` with the matched request id when unlocked.

## Wrong-code handling (critical ordering detail)
The brief is explicit and correct here: **do not `raise` on a wrong
code.** If the attempt counter is incremented in the same ORM
transaction that then raises `UserError`, Odoo rolls the whole
transaction back — including the counter write — so three wrong
attempts would never actually reach 3. `action_enter_code()` therefore:
opens its own cursor (`self.pool.cursor()`, same pattern as the existing
`_otm_log_export`) to write `attempts += 1` (and `state='locked'` on the
3rd), commits that on its own, writes the matching log row on that same
isolated cursor, and only then returns an `ir.actions.client` /
`display_notification` with type `danger` describing the failure —
never an exception. A *correct* code still returns normally via the
regular transaction (nothing to protect there).

## Cron
`ir.cron`, every 1 minute, calls a model method that: expires `approved`
requests past `code_expiry`, and expires `sent` requests older than 60
minutes (spec.md Open Question 1) — both logged `expired`.

## Hooks (`__init__.py`, extending the existing single-env hooks)
`post_init_hook(env)` additionally:
- Checks whether `base.group_user` currently implies
  `base.group_allow_export` in this database (`allow in user_grp.implied_ids`
  — already how the existing hook detects this).
- If yes: removes that implication, and removes `base.group_allow_export`
  from every user not in `group_lead_export` (both already present in the
  existing hook — unchanged).
- `group_lead_export`'s own `implied_ids` already includes both
  `base.group_user` and `base.group_allow_export` (unchanged from the
  existing `security.xml`).
- `base.user_admin` is added to `group_lead_export` on install (unchanged
  from the existing hook).
`uninstall_hook(env)` restores the implication and gives every non-share
user back `base.group_allow_export` (unchanged from the existing hook).
Nothing here needed new logic — the existing hooks already did exactly
what this phase's brief asks; only the *rest* of the module is new.

## Menus
**Corrected during the analyze pass (T23):** this plan originally kept
the existing *Lead Export* menu parented under `base.menu_administration`
(that's where the pre-unlock-feature version of the module put it, and
it was fine there since both its children were admin-only). Checked
against the actual Odoo 17.0 source
(`odoo/addons/base/views/base_menus.xml`) and found `base.menu_administration`
itself carries `groups_id = [group_system, group_erp_manager]` — so a
standalone Approver (spec.md Open Question 5 — a Director who need not
be an admin or even a `group_lead_export` member) would never see the
*Settings* app at all, making *Approvals* unreachable for exactly the
people who most need it. Fixed: *Lead Export* is now its own bare
top-level menu (no `parent`, same pattern `custom_leads` itself uses for
its "Leads" menu), `groups="base.group_user"` so every internal user can
see it. Children self-restrict instead: *Request Export* and *Export
Requests* → `group_lead_export` (+ `base.group_system` for the latter, so
admins can audit everyone's); *Approvals* → no menu-level `groups` at
all, gated purely inside the wizard's own eligibility check (an approver
may hold no other group whatsoever); *Approvers*, *Export Access*,
*Export Log* → `base.group_system` only, unchanged in spirit from before.

## Security
`ir.rule` on `otm.lead.export.request`, no `groups` (global, i.e. applies
to everyone, combined per Odoo's normal AND/OR rule-combination logic):
```python
domain_force = "[(1,'=',1)] if user.has_group('base.group_system') else [('user_id','=',user.id)]"
```
— exactly the expression the brief specifies, verbatim. This alone would
NOT let an approver (who isn't `group_system` and isn't the requester)
see someone else's pending request through a plain list view — and
that's intentional: per spec.md Open Question 3, "Approvals" is a wizard
that reads with `sudo()` after checking approver-eligibility in code, so
it never depends on this rule granting cross-user visibility at all. ACL
rows: every new model gets read/write/create/unlink rows scoped to
`base.group_system` for full admin, plus narrower rows for
`group_lead_export` (own requests only, enforced by the rule above, not
by ACL) and for TransientModel wizards (always group_lead_export +
group_system, create/read only, no write/unlink needed on wizards).

## Odoo 17 specifics applied
- `res.users` groups field is `groups_id` (confirmed from
  `odoo/addons/base/models/res_users.py` in the 17.0 source — matches
  the existing module's own already-correct usage).
- Views use `<tree>`, never `<list>` (confirmed from
  `ir_ui_view.py`'s accepted arch root tags in 17.0).
- `invisible="<python expr>"` as a direct attribute (no `attrs=`
  wrapper) is valid in 17.0 — 17.0 is the version that introduced this
  replacing `attrs`/`states`. Used directly, no `attrs` dict needed
  anywhere in this feature's views.
- `ir.rule.groups` (not `groups_id`) confirmed from `ir_rule.py` in the
  17.0 source — matches the brief.
- Hook signature: single `env` argument — see "Corrected from the
  brief" above.

## Risks
| Risk | Mitigation |
|---|---|
| Hook signature mismatch (brief said `(cr, registry)`) | Verified against actual 17.0 source; used the correct single-`env` form (already what the existing module does). |
| Wrong-code counter lost to transaction rollback | Isolated cursor for the attempt write, no `raise` on wrong code — see "Wrong-code handling". |
| Stale `ir.model.access` cache after install | Service restart required after `-u`; called out in deploy steps. |
| Code visible to anyone with raw DB access during the brief pending window | Accepted, documented limitation (constitution.md) — not claimed to be solved; would need real secret-management infra to close. |
| Telegram notify silently doing nothing | Off by default, explicitly flagged in spec.md and the test checklist so it isn't mistaken for working. |
| `custom_leads`'s own `export_data()` override interacting with this one | Traced the MRO explicitly (see "Enforcement") — confirmed safe, no file in `custom_leads` touched. |
| Nothing in this plan has run against a live server | Stated plainly in constitution.md and in the delivery notes — only `py_compile`/XML-parse validated here. |
| `base.menu_administration` is admin-only, which would have hidden *Approvals* from non-admin Approvers | Found during the analyze pass; *Lead Export* is now a bare top-level menu instead — see "Menus" above. |
| No log `result` value exists for "code revealed/approved" specifically | The brief's own result vocabulary (US7) lists exactly 7 values with no "approved" entry. Reused `requested` for the reveal event too, distinguished only by its `note` text ("Code revealed by …"). Flagged as spec.md Open Question 6 rather than silently inventing an 8th value outside the given list. |
| `views/res_config_settings_views.xml` failed to install (`ParseError: Element '<xpath expr="//div[hasclass('settings')]">' cannot be located in parent view`) — reported by the user after a real `-u` install attempt | `base.res_config_settings_view_form` ships completely empty in Odoo 17.0 (verified: `<form ...></form>`, no children) — there is no `div.settings` to target; that was a pre-17 convention. Fixed by following the pattern Odoo 17 core itself uses (confirmed in `addons/crm/views/res_config_settings_views.xml`): inherit the bare form, `xpath expr="//form" position="inside"`, add a fresh `<app>`/`<block>`/`<setting>` tab. This is the one part of the delivery that *was* exercised against a real server, and it failed — correction applied and documented here rather than left as a one-line fix with no record. |
| Clicking the "Lead Export" app icon only ever opened the *Request Export* popup — reported by the user after real install/testing | `menu_lead_export_root` had no `action` of its own, so Odoo fell back to auto-opening the first child action visible to that user — sequence 1 was *Request Export*, a `target="new"` wizard, so the app icon always landed in a modal instead of a page, with the tab bar never reached. Fixed by giving the root menu its own explicit `action="action_lead_export_request"` (a plain full-page list, never a popup) so the landing behaviour is deterministic regardless of child order/visibility. Required widening `otm.lead.export.request`'s ACL with a read-only row for `base.group_user` (everyone) so a standalone Approver with no other group lands on an empty list rather than an `AccessError` — `rule_otm_lead_export_request_own` already scopes the actual rows safely to "their own, or all for admins". |
| After submitting a request, nothing opened except a toast — user expected the request's own form (with the "Enter Code" button) to open automatically, as in the Odoo 19 version | `action_submit` only ever returned `display_notification`, never a redirect. Fixed by chaining `params.next` on the notification to an `ir.actions.act_window` opening the new request's own form (`target: "current"`) — the toast shows first, then the client follows `next`. Applied the same fix to the Enter Code wizard's success path (`params.next: {'type': 'ir.actions.act_window_close'}` only when the code was correct) so that dialog closes and the request form behind it refreshes to show the new `unlocked_until`; a wrong/locked code leaves the dialog open to retry. |
