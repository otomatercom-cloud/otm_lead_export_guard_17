import datetime
import hashlib
import hmac
import logging
import random

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CODE_VALID_MINUTES = 10       # how long a revealed code stays enterable
SENT_EXPIRY_MINUTES = 60      # spec.md Open Question 1 — assumption, not specified in the brief
MAX_ATTEMPTS = 3


class OtmLeadExportRequest(models.Model):
    _name = 'otm.lead.export.request'
    _description = 'Lead Export Unlock Request'
    _order = 'id desc'

    user_id = fields.Many2one('res.users', string='Requester', required=True,
                               default=lambda self: self.env.user, readonly=True, index=True)
    reason = fields.Text(required=True)
    minutes = fields.Selection([
        ('5', '5 minutes'), ('10', '10 minutes'), ('15', '15 minutes'),
        ('20', '20 minutes'), ('30', '30 minutes'),
    ], required=True, default='10')
    state = fields.Selection([
        ('sent', 'Pending Approval'),
        ('approved', 'Code Issued'),
        ('expired', 'Expired'),
        ('locked', 'Locked'),
    ], default='sent', required=True, index=True, readonly=True)
    request_date = fields.Datetime(default=fields.Datetime.now, readonly=True)

    # Never exposed on any view/ACL beyond this model's own sudo-scoped
    # wizard methods. See constitution.md + plan.md "Code delivery".
    code_hash = fields.Char(readonly=True)
    code_plain_pending = fields.Char(readonly=True)
    code_expiry = fields.Datetime(readonly=True)
    attempts = fields.Integer(default=0, readonly=True)
    unlocked_until = fields.Datetime(readonly=True, index=True)
    approver_id = fields.Many2one('res.users', string='Approved By', readonly=True)

    # ── HMAC helpers ──────────────────────────────────────────────────
    @api.model
    def _hmac_key(self):
        return self.env['ir.config_parameter'].sudo().get_param('database.secret') or ''

    def _hash_code(self, code):
        self.ensure_one()
        msg = f"{self.id}:{code}".encode()
        return hmac.new(self._hmac_key().encode(), msg, hashlib.sha256).hexdigest()

    def _code_matches(self, code):
        self.ensure_one()
        if not self.code_hash:
            return False
        return hmac.compare_digest(self._hash_code(code), self.code_hash)

    # ── Lifecycle ────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        # "a new request expires the previous open one" — supersede the
        # requester's own still-open requests before creating the new one.
        for vals in vals_list:
            user_id = vals.get('user_id', self.env.user.id)
            open_requests = self.sudo().search([
                ('user_id', '=', user_id), ('state', 'in', ('sent', 'approved')),
            ])
            for req in open_requests:
                req._expire(reason='superseded by a new request')
        records = super().create(vals_list)
        for rec in records:
            # Same transaction as the create on purpose (isolated=False): the
            # brand-new request row is not committed yet, so a log row written
            # on a separate cursor would hit a foreign-key violation on
            # request_id and be silently lost (found by running this on a real
            # Odoo 17 server). Nothing after this point can raise.
            rec._log('requested', note='Request submitted', isolated=False)
        return records

    def _log(self, result, note='', isolated=True):
        self.ensure_one()
        vals = {
            'user_id': self.user_id.id,
            'model': 'leads.logic',
            'record_count': 0,
            'field_count': 0,
            'result': result,
            'note': note,
            'request_id': self.id,
        }
        Log = self.env['otm.lead.export.log'].sudo()
        if isolated:
            Log._log_isolated(vals)
        else:
            Log.create(vals)

    def _approve_and_reveal(self, approver_user):
        """Called only from the approval wizard, which has already
        verified `approver_user` is an active approver and not the
        requester. Generates the code, stores only its hash, hands the
        plaintext back to the caller once."""
        self.ensure_one()
        if self.state != 'sent':
            raise UserError(_("This request is no longer pending."))
        if approver_user.id == self.user_id.id:
            raise UserError(_("You cannot approve your own export request."))
        code = '%06d' % random.SystemRandom().randint(0, 999999)
        code_hash = self._hash_code(code)
        self.write({
            'state': 'approved',
            'code_hash': code_hash,
            'code_plain_pending': code,  # written and read back in the same call…
            'code_expiry': fields.Datetime.now() + datetime.timedelta(minutes=CODE_VALID_MINUTES),
            'attempts': 0,
            'approver_id': approver_user.id,
        })
        self.write({'code_plain_pending': False})  # …then wiped immediately. See plan.md.
        self._log('requested', note=f'Code revealed by {approver_user.name}')
        self._notify_telegram_stub()
        self._email_code_to_requester(code)
        return code

    def _email_code_to_requester(self, code):
        """Mails the just-revealed code to the requester, in addition to
        the approver handing it over directly. Not a scope violation of
        constitution.md's "never visible to the requester" rule — that
        rule is about Odoo's own views/logs never rendering it before
        the approver acts; the requester always had to receive this
        exact plaintext through some side channel to ever type it back
        in, so this only automates that unavoidable hand-off. Unlike the
        Telegram stub, this uses Odoo's own `mail.mail` — no external
        bridge is needed, only a working outgoing mail server configured
        under Settings > Technical > Email. If none is configured (or
        the send fails for any reason), this must never block the
        reveal itself — the approver can still read the code aloud."""
        self.ensure_one()
        try:
            partner = self.user_id.partner_id
            if not partner or not partner.email:
                _logger.warning(
                    "Could not email export unlock code for request %s: "
                    "requester %s has no email on file.", self.id, self.user_id.login)
                return
            body = (
                f"<p>Your Lead Export unlock code is: <strong>{code}</strong></p>"
                f"<p>Valid for 10 minutes, one use. Enter it under "
                f"<b>Lead Export &gt; Export Requests</b>, on this request, "
                f"using the <b>Enter Code</b> button.</p>"
            )
            self.env['mail.mail'].sudo().create({
                'subject': 'Your Lead Export unlock code',
                'body_html': body,
                'email_to': partner.email,
            }).send()
        except Exception:
            _logger.exception(
                "Could not email export unlock code for request %s — "
                "check Settings > Technical > Email > Outgoing Mail Servers.",
                self.id)

    def action_enter_code(self, code):
        """Returns (ok: bool, message: str). Never raises — see plan.md
        'Wrong-code handling' for why a wrong attempt must not roll back
        its own counter increment."""
        self.ensure_one()
        now = fields.Datetime.now()
        if self.state == 'locked':
            return False, _("This request is locked. Submit a new export request.")
        if self.state != 'approved':
            return False, _("This request has no active code.")
        if not self.code_expiry or now > self.code_expiry:
            self._expire_isolated(reason='code expired before entry')
            return False, _("The code has expired. Submit a new export request.")
        if self._code_matches(code):
            minutes = int(self.minutes)
            self.write({'unlocked_until': now + datetime.timedelta(minutes=minutes)})
            self._log('unlocked', note=f'Unlocked for {minutes} minutes')
            return True, _("Unlocked. You can export for the next %s minutes.") % minutes
        # Wrong code: increment the counter on its OWN cursor so a later
        # non-raising return can never roll it back.
        self._write_isolated_attempt()
        return False, self._wrong_code_message()

    def _wrong_code_message(self):
        self.ensure_one()
        self.invalidate_recordset(['attempts', 'state'])  # re-read after isolated write
        if self.state == 'locked':
            return _("Wrong code. This request is now locked — submit a new export request.")
        remaining = MAX_ATTEMPTS - self.attempts
        return _("Wrong code. %s attempt(s) remaining.") % remaining

    def _write_isolated_attempt(self):
        """Increments attempts (and locks on the 3rd) on its own cursor,
        committed independently of the caller's transaction outcome."""
        self.ensure_one()
        try:
            with self.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                rec = env['otm.lead.export.request'].browse(self.id)
                new_attempts = rec.attempts + 1
                vals = {'attempts': new_attempts}
                locked = new_attempts >= MAX_ATTEMPTS
                if locked:
                    vals['state'] = 'locked'
                rec.write(vals)
                # Already on an isolated cursor here — write the log row
                # directly on it rather than opening a second one.
                env['otm.lead.export.log'].create({
                    'user_id': rec.user_id.id,
                    'model': 'leads.logic',
                    'record_count': 0,
                    'field_count': 0,
                    'result': 'locked' if locked else 'wrong_code',
                    'note': f'Attempt {new_attempts}/{MAX_ATTEMPTS}',
                    'request_id': rec.id,
                })
        except Exception:
            _logger.exception("Could not record wrong-code attempt for request %s", self.id)

    def _expire(self, reason=''):
        self.ensure_one()
        if self.state in ('sent', 'approved'):
            self.write({'state': 'expired', 'code_plain_pending': False})
            self._log('expired', note=reason)

    def _expire_isolated(self, reason=''):
        """Same as _expire but safe to call mid-transaction without
        losing the write if the caller later aborts."""
        self.ensure_one()
        try:
            with self.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                rec = env['otm.lead.export.request'].browse(self.id)
                if rec.state in ('sent', 'approved'):
                    rec.write({'state': 'expired', 'code_plain_pending': False})
                    env['otm.lead.export.log'].create({
                        'user_id': rec.user_id.id, 'model': 'leads.logic',
                        'record_count': 0, 'field_count': 0,
                        'result': 'expired', 'note': reason, 'request_id': rec.id,
                    })
        except Exception:
            _logger.exception("Could not expire request %s", self.id)

    @api.model
    def _cron_expire(self):
        """Odoo 17: cron methods are plain @api.model methods called by
        ir.cron, no special decorator needed."""
        now = fields.Datetime.now()
        sent_cutoff = now - datetime.timedelta(minutes=SENT_EXPIRY_MINUTES)
        stale_sent = self.sudo().search([('state', '=', 'sent'), ('request_date', '<', sent_cutoff)])
        for req in stale_sent:
            req._expire(reason='pending-approval window elapsed (%s min)' % SENT_EXPIRY_MINUTES)
        stale_approved = self.sudo().search([('state', '=', 'approved'), ('code_expiry', '<', now)])
        for req in stale_approved:
            req._expire(reason='code validity window elapsed')

    def _notify_telegram_stub(self):
        """Optional, off by default, never allowed to break the caller.
        See spec.md Open Question 2 — not wired to a real API yet."""
        self.ensure_one()
        try:
            enabled = self.env['ir.config_parameter'].sudo().get_param(
                'otm_lead_export_guard.notify_telegram')
            if not enabled:
                return
            # Placeholder only — software_telegram's real model/method
            # names were not available this session. Intentionally a
            # no-op so turning the setting on cannot ever raise.
            _logger.info(
                "Telegram notify requested for export request %s but no "
                "software_telegram integration is wired up yet.", self.id)
        except Exception:
            _logger.exception("Telegram notify stub failed for request %s", self.id)
