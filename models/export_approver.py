from odoo import fields, models


class OtmLeadExportApprover(models.Model):
    _name = 'otm.lead.export.approver'
    _description = 'Lead Export Approver (Director)'
    _order = 'id desc'
    _rec_name = 'name'

    user_id = fields.Many2one('res.users', string='Director', required=True,
                               ondelete='cascade')
    name = fields.Char(related='user_id.name', store=True, readonly=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('user_unique', 'unique(user_id)', 'This user is already an approver.'),
    ]
