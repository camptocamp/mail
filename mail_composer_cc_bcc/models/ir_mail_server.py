# Copyright 2024 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class IrMailServer(models.Model):
    _inherit = "ir.mail_server"

    def _prepare_email_message__(self, message, smtp_session):  # noqa: PLW3201
        """Make sure a composer email is only sent to its own recipient.

        Each recipient gets its own email, see ``MailMail._prepare_outgoing_list``.
        Since 19.0 Odoo restricts the SMTP envelope through the
        ``send_validated_to`` context key, which ``MailMail._send`` fills with the
        normalized email of the recipient of that very email. Without it,
        ``_prepare_smtp_to_list`` falls back to To + Cc + Bcc, which would send
        duplicate emails and leak the Bcc recipients: refuse to send instead.

        This is the 19.0 counterpart of the ``recipients`` context guard added in
        OCA/mail#233 for 18.0.
        """
        smtp_from, smtp_to_list, message = super()._prepare_email_message__(
            message, smtp_session
        )

        if self.env.context.get("is_from_composer") and not self.env.context.get(
            "send_validated_to"
        ):
            raise ValueError("Could not determine the recipient of this email")

        _logger.debug("smtp_to_list: %s", smtp_to_list)
        return smtp_from, smtp_to_list, message
