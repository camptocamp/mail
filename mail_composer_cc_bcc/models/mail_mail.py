# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


import os

from odoo import fields, models, tools

from odoo.addons.base.models.ir_mail_server import extract_rfc2822_addresses


def format_emails(partners):
    return [tools.formataddr((p.name or "", p.email)) for p in partners if p.email]


def format_emails_raw(partners):
    return [p.email for p in partners if p.email]


def format_emails_str(partners):
    emails = format_emails(partners)
    return ", ".join(emails)


class MailMail(models.Model):
    _inherit = "mail.mail"

    email_bcc = fields.Char("Bcc", help="Blind Cc message recipients")

    def _expose_bcc_marker(self):
        """Whether to also add the informational ``X-Odoo-Bcc`` marker header.

        Disabled by default: the marker survives sending and would expose the
        bcc recipient on every copy. Enable it through the ``expose_x_odoo_bcc``
        context key or the ``EXPOSE_X_ODOO_BCC`` environment variable.
        """
        if self.env.context.get("expose_x_odoo_bcc"):
            return True
        return tools.str2bool(os.environ.get("EXPOSE_X_ODOO_BCC") or "", False)

    def _prepare_outgoing_list(
        self, mail_server=False, recipients_follower_status=None
    ):
        # First, return if we're not coming from the Mail Composer
        res = super()._prepare_outgoing_list(
            mail_server=mail_server,
            recipients_follower_status=recipients_follower_status,
        )
        is_out_of_scope = len(self.ids) > 1
        is_from_composer = self.env.context.get("is_from_composer", False)

        if is_out_of_scope or not is_from_composer:
            return res

        # Prepare values for To, Cc headers
        partners_cc_bcc = self.recipient_cc_ids + self.recipient_bcc_ids
        partner_to_ids = [r.id for r in self.recipient_ids if r not in partners_cc_bcc]
        partner_to = self.env["res.partner"].browse(partner_to_ids)
        email_to = format_emails(partner_to)  # recipient_ids - cc - bcc
        email_to_raw = format_emails_raw(partner_to)
        email_cc = format_emails_str(self.recipient_cc_ids)
        email_bcc = [r.email for r in self.recipient_bcc_ids if r.email]

        # Collect recipients (RCPT TO) and update all emails
        # with the same To, Cc headers (to be shown by email client as users expect)
        recipients = set()
        cc_only_index = None
        for index, m in enumerate(res):
            rcpt_to = None
            if m["email_to"]:
                rcpt_to = extract_rfc2822_addresses(m["email_to"][0])[0]

                # If the recipient is a Bcc, set a real Bcc header.
                # _prepare_email_message uses it to build the envelope
                # and then strips it, so it never leaks.
                if rcpt_to in email_bcc:
                    # Avoid mutating the shared headers by making a copy
                    m["headers"] = {**m["headers"], "Bcc": m["email_to"][0]}
                    # Optional legacy marker. Unlike Bcc it survives sending,
                    # so only add it when explicitly enabled (it would expose
                    # the bcc recipient otherwise).
                    if self._expose_bcc_marker():
                        m["headers"]["X-Odoo-Bcc"] = m["email_to"][0]

            # in the absence of self.email_to, Odoo creates one special mail for CC
            # see https://github.com/odoo/odoo/commit/46bad8f0
            elif m["email_cc"]:
                rcpt_to = extract_rfc2822_addresses(m["email_cc"][0])[0]
                cc_only_index = index

            if rcpt_to:
                recipients.add(rcpt_to)

            m.update(
                {
                    "email_to": email_to,
                    "email_to_raw": email_to_raw,
                    "email_cc": email_cc,
                }
            )

        self.env.context = {**self.env.context, "recipients": list(recipients)}

        # Drop the synthetic CC-only mail Odoo adds to avoid duplicates.
        if cc_only_index is not None and len(res) > len(recipients):
            res.pop(cc_only_index)

        return res
