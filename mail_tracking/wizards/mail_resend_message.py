# Copyright 2019 Alexandre Díaz
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import Command, api, models


class MailResendMessage(models.TransientModel):
    _inherit = "mail.resend.message"

    @api.model
    def default_get(self, fields):
        rec = super().default_get(fields)
        message_id = self._context.get("mail_message_to_resend")
        if not message_id:
            return rec
        mail_message = self.env["mail.message"].browse(message_id)
        failed_states = self.env["mail.message"].get_failed_states()
        tracking_ids = mail_message.mail_tracking_ids.filtered(
            lambda x: x.state in failed_states
        )
        if tracking_ids:
            partner_values = []
            for tracking in tracking_ids:
                notification = mail_message.notification_ids.filtered(
                    lambda x, tracking=tracking: x.res_partner_id == tracking.partner_id
                )
                existing_resend_partner = self.env["mail.resend.partner"].search(
                    [("notification_id", "=", notification.id)]
                )
                if existing_resend_partner:
                    continue
                # Create only resends that mail.notification didn't prepare already
                partner_values.append(
                    {
                        "notification_id": notification.id,
                        "resend": True,
                        "message": tracking.error_description,
                    }
                )
            if partner_values:
                partner_ids = self.env["mail.resend.partner"].create(partner_values).ids
                partner_commands = [
                    Command.link(partner_id) for partner_id in partner_ids
                ]
                rec["partner_ids"].extend(partner_commands)
        return rec
