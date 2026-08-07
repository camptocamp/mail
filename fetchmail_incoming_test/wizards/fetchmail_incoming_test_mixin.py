# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models


class FetchmailIncomingTestMixin(models.AbstractModel):
    _name = "fetchmail.incoming.test.mixin"
    _description = "Simulate an Incoming Email"

    def _build_raw_message(self):
        """Return the incoming email as raw bytes, as a mail server would."""
        raise NotImplementedError

    def action_process(self):
        """Feed the email to the mail gateway as a real inbound one."""
        self.ensure_one()
        thread_id = self.env["mail.thread"].message_process(
            None, self._build_raw_message()
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Email processed"),
                "message": _("The gateway created record #%s.", thread_id),
                "sticky": False,
                # Close the wizard dialog once the notification is shown.
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
