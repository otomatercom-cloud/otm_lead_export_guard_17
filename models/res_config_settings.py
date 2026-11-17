from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    otm_export_notify_telegram = fields.Boolean(
        string='Notify approvers on Telegram',
        config_parameter='otm_lead_export_guard.notify_telegram',
        help="Off by default. See the module's spec.md Open Question 2: "
             "this currently has no real Telegram integration wired up — "
             "turning it on changes nothing yet, it only reserves the "
             "setting for a future release.")
