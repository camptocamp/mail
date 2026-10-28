# Copyright 2023 Camptocamp
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import hashlib
import inspect

from odoo import Command, tools
from odoo.tests import Form, tagged

from odoo.addons.base.models.ir_mail_server import extract_rfc2822_addresses
from odoo.addons.mail.tests.common import MailCase
from odoo.addons.mail.tests.test_mail_composer import TestMailComposerForm
from odoo.addons.mail.wizard.mail_compose_message import (
    MailComposeMessage as MailComposer_upstream,
)

VALID_HASHES = {
    "mail.composer:_compute_partner_ids": ["c3903ab78bf2e5d9aba078ac2689d974"],
}


class MailComposerCcBccMixin:
    @classmethod
    def _setup_mail_composer_cc_bcc_data(cls):
        env = cls.env
        cls.partner = env["res.partner"].create(
            {
                "name": "partner",
                "email": "partner@example.com",
            }
        )
        cls.partner_cc = env["res.partner"].create(
            {
                "name": "partner_cc",
                "email": "partner_cc@example.com",
            }
        )
        cls.partner_cc2 = env["res.partner"].create(
            {
                "name": "partner_cc2",
                "email": "partner_cc2@example.com",
            }
        )
        cls.partner_cc3 = env["res.partner"].create(
            {
                "name": "partner_cc3",
                "email": "partner_cc3@example.com",
            }
        )
        cls.partner_bcc = env["res.partner"].create(
            {
                "name": "partner_bcc",
                "email": "partner_bcc@example.com",
            }
        )


class TestMailCcBcc(TestMailComposerForm, MailComposerCcBccMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_mail_composer_cc_bcc_data()

    def open_mail_composer_form(self):
        # Use form to populate data
        test_record = self.test_record.with_env(self.env)
        ctx = {
            "default_partner_ids": test_record.ids,
            "default_model": test_record._name,
            "default_res_ids": test_record.ids,
            # to ensure consistent test results even when mail_post_defer is installed
            "mail_notify_force_send": True,
        }
        form = Form(self.env["mail.compose.message"].with_context(**ctx))
        form.body = "<p>Hello</p>"
        return form

    def test_MailComposer_upstream_file_hash(self):
        """Test that copied upstream function hasn't received fixes"""
        _compute_partner_ids = inspect.getsource(
            MailComposer_upstream._compute_partner_ids
        ).encode()
        func_hash = hashlib.md5(_compute_partner_ids).hexdigest()
        self.assertIn(func_hash, VALID_HASHES.get("mail.composer:_compute_partner_ids"))

    def test_email_cc_bcc(self):
        self.test_record.email = "test@example.com"
        form = self.open_mail_composer_form()
        composer = form.save()
        # Use object to update Many2many fields (form can't do like this)
        composer.partner_cc_ids = self.partner_cc
        composer.partner_cc_ids |= self.partner_cc2
        composer.partner_cc_ids |= self.partner_cc3
        composer.partner_bcc_ids = self.partner_bcc

        with self.mock_mail_gateway():
            composer._action_send_mail()

        self.assertEqual(len(self._mails), 5)

        # Verify recipients of mail.message
        message = self.test_record.message_ids[0]

        # only keep 1 email to avoid clutting db
        # but actually send 1 mail per recipients
        self.assertEqual(len(message.mail_ids), 1)
        self.assertEqual(len(message.recipient_cc_ids), 3)
        self.assertEqual(len(message.recipient_bcc_ids), 1)
        # Verify notification
        for_message = [
            ("mail_message_id", "=", message.id),
            ("notification_type", "=", "email"),
        ]
        notif = self.env["mail.notification"].search(for_message)
        self.assertEqual(len(notif), 5)

        # Verify data of mail.mail
        mail = message.mail_ids
        expecting = ", ".join(
            [
                '"partner_cc" <partner_cc@example.com>',
                '"partner_cc2" <partner_cc2@example.com>',
                '"partner_cc3" <partner_cc3@example.com>',
            ]
        )
        self.assertEqual(mail.email_cc, expecting)
        expecting = '"partner_bcc" <partner_bcc@example.com>'
        self.assertEqual(mail.email_bcc, expecting)

    def test_email_cc_bcc_one_email_per_recipient(self):
        """Every recipient gets exactly one email, and no Bcc address leaks.

        Regression test: the Cc-only email Odoo builds when ``mail.email_to``
        is empty is a duplicate here, and dropping it by length (``res.pop()``)
        removed the *last* recipient instead, silently losing an email.
        """
        partner_bcc2 = self.env["res.partner"].create(
            {"name": "partner_bcc2", "email": "partner_bcc2@example.com"}
        )
        self.test_record.email = "test@example.com"
        form = self.open_mail_composer_form()
        composer = form.save()
        composer.partner_cc_ids = self.partner_cc
        composer.partner_cc_ids |= self.partner_cc2
        composer.partner_bcc_ids = self.partner_bcc
        composer.partner_bcc_ids |= partner_bcc2

        with self.mock_mail_gateway():
            composer._action_send_mail()

        # 1 To + 2 Cc + 2 Bcc = 5 recipients, 5 emails, no duplicate, none lost
        self.assertEqual(len(self._mails), 5)

        bcc_emails = {self.partner_bcc.email, partner_bcc2.email}
        expected_cc = ", ".join(
            [
                '"partner_cc" <partner_cc@example.com>',
                '"partner_cc2" <partner_cc2@example.com>',
            ]
        )
        seen_bcc = set()
        for mail in self._mails:
            headers = mail.get("headers") or {}
            # The To / Cc headers are the same on every email...
            self.assertEqual(mail["email_cc"], expected_cc)
            # ... and never expose a Bcc recipient
            visible = f"{mail['email_to']} {mail['email_cc']}"
            for bcc_email in bcc_emails:
                self.assertNotIn(bcc_email, visible)
            # the informational marker must not be set by default: unlike Bcc
            # it is not stripped before sending (OCA/mail#233)
            self.assertNotIn("X-Odoo-Bcc", headers)
            if headers.get("Bcc"):
                seen_bcc.add(extract_rfc2822_addresses(headers["Bcc"])[0])

        # each Bcc recipient got its own email
        self.assertEqual(seen_bcc, bcc_emails)

    def test_email_cc_bcc_no_reply_all_header(self):
        """'X-Msg-To-Add' must not survive: 19.0 merges it into the To header.

        ``MailThread._notify_by_email_get_headers`` fills it with every external
        recipient and ``IrMailServer._alter_message__`` merges it into ``To`` at
        send time to enable Reply-All, which would disclose the Bcc recipients.
        """
        self.test_record.email = "test@example.com"
        form = self.open_mail_composer_form()
        composer = form.save()
        composer.partner_cc_ids = self.partner_cc
        composer.partner_bcc_ids = self.partner_bcc

        with self.mock_mail_gateway():
            composer._action_send_mail()

        for mail in self._mails:
            self.assertNotIn("X-Msg-To-Add", mail.get("headers") or {})

    def test_email_cc_bcc_marker_opt_in(self):
        """The 'X-Odoo-Bcc' marker is only added when explicitly enabled."""
        self.test_record.email = "test@example.com"
        form = self.open_mail_composer_form()
        composer = form.save()
        composer.partner_cc_ids = self.partner_cc
        composer.partner_bcc_ids = self.partner_bcc

        with self.mock_mail_gateway():
            composer.with_context(expose_x_odoo_bcc=True)._action_send_mail()

        markers = [
            (mail.get("headers") or {}).get("X-Odoo-Bcc")
            for mail in self._mails
            if (mail.get("headers") or {}).get("X-Odoo-Bcc")
        ]
        self.assertEqual(len(markers), 1)
        self.assertIn(self.partner_bcc.email, markers[0])

    def test_email_cc_bcc_recipient_without_email(self):
        """A recipient with no email must not take the whole mail.mail down.

        Core builds a '"Name" <@False>' placeholder for such a partner, from
        which no address can be extracted; indexing it blindly raised
        IndexError and nobody received the message.
        """
        partner_no_email = self.env["res.partner"].create({"name": "No Email"})
        mail = self.env["mail.mail"].create(
            {
                "subject": "test",
                "body_html": "<p>test</p>",
                "recipient_ids": [
                    Command.set((self.partner_cc + partner_no_email).ids)
                ],
            }
        )

        outgoing = mail.with_context(is_from_composer=True)._prepare_outgoing_list()

        # no exception, and one entry per recipient
        self.assertEqual(len(outgoing), 2)

        # the placeholder entry is left exactly as core built it, so that core
        # finds no SMTP recipient for it, raises NO_VALID_RECIPIENT and skips
        # only this one
        placeholder = [e for e in outgoing if "No Email" in str(e["email_to"])]
        self.assertEqual(len(placeholder), 1)
        self.assertEqual(placeholder[0]["email_to"], ['"No Email" <@False>'])

        # while the valid recipient did get the module's shared To header
        valid = [e for e in outgoing if e is not placeholder[0]]
        self.assertEqual(len(valid), 1)
        self.assertIn("partner_cc@example.com", str(valid[0]["email_to"]))

    def test_template_cc_bcc(self):
        env = self.env
        # Company default values
        env.company.default_partner_cc_ids = self.partner_cc3
        env.company.default_partner_bcc_ids = self.partner_cc2
        # Partner template values
        tmpl_model = env["ir.model"].search([("model", "=", "res.partner")])
        partner_cc = self.partner_cc
        partner_bcc = self.partner_bcc
        vals = {
            "name": "Product Template: Re: [E-COM11] Cabinet with Doors",
            "model_id": tmpl_model.id,
            "subject": "Re: [E-COM11] Cabinet with Doors",
            "body_html": """<p style="margin:0px 0 12px 0;box-sizing:border-box;">
Test Template<br></p>""",
            "email_cc": tools.formataddr(
                (partner_cc.name or "False", partner_cc.email or "False")
            ),
            "email_bcc": tools.formataddr(
                (partner_bcc.name or "False", partner_bcc.email or "False")
            ),
            "use_default_to": False,
        }
        partner_tmpl = env["mail.template"].create(vals)

        # Open mail composer form and check for default values from company
        form = self.open_mail_composer_form()
        composer = form.save()

        self.assertEqual(composer.partner_cc_ids, self.partner_cc3)
        self.assertEqual(composer.partner_bcc_ids, self.partner_cc2)

        # Change email template and check for values from it
        form.template_id = partner_tmpl
        composer = form.save()

        # Beside existing Cc and Bcc, add template's ones
        form = Form(composer)
        form.template_id = partner_tmpl
        composer = form.save()
        expecting = self.partner_cc3 + self.partner_cc

        self.assertEqual(composer.partner_cc_ids, expecting)
        expecting = self.partner_cc2 + self.partner_bcc
        self.assertEqual(composer.partner_bcc_ids, expecting)
        # But not add Marc Demo from cc field to partner_ids field
        self.assertEqual(len(composer.partner_ids), 1)
        self.assertEqual(composer.partner_ids.display_name, "Test")

        # Selecting the template again doesn't add as the partners already
        # in the list
        form = Form(composer)
        form.template_id = env["mail.template"]
        form.save()
        self.assertFalse(form.template_id)  # no template

        form.template_id = partner_tmpl
        composer = form.save()

        expecting = self.partner_cc3 + self.partner_cc
        self.assertEqual(composer.partner_cc_ids, expecting)

        expecting = self.partner_cc2 + self.partner_bcc
        self.assertEqual(composer.partner_bcc_ids, expecting)

    def test_template_cc_bcc_with_placeholders(self):
        """Test mail template with placeholders for email_cc and email_bcc"""
        # Add child record to test_record
        self.test_record.child_ids |= (
            self.partner_cc + self.partner_cc2 + self.partner_cc3
        )

        # Partner template values
        tmpl_model = self.env["ir.model"].search([("model", "=", "res.partner")])
        vals = {
            "name": "Product Template: Re: [E-COM11] Cabinet with Doors",
            "model_id": tmpl_model.id,
            "subject": "Re: [E-COM11] Cabinet with Doors",
            "body_html": """<p style="margin:0px 0 12px 0;box-sizing:border-box;">
Test Template<br></p>""",
            # Use placeholders
            "email_cc": "{{ ','.join(object.mapped('child_ids.email')) }}",
            "email_bcc": "{{ ','.join(object.mapped('child_ids.email')) }}",
            "use_default_to": False,
        }
        partner_tmpl = self.env["mail.template"].create(vals)

        # Open mail composer form and check for default values from company
        form = self.open_mail_composer_form()
        composer = form.save()

        form = Form(composer)
        form.template_id = partner_tmpl
        composer = form.save()
        expecting = self.partner_cc + self.partner_cc2 + self.partner_cc3

        self.assertEqual(composer.partner_cc_ids, expecting)
        self.assertEqual(composer.partner_bcc_ids, expecting)
        # But not add Marc Demo from cc field to partner_ids field
        self.assertEqual(len(composer.partner_ids), 1)
        self.assertEqual(composer.partner_ids.display_name, "Test")

        # Selecting the template again doesn't add as the partners already
        # in the list
        form = Form(composer)
        form.template_id = self.env["mail.template"]
        form.save()
        self.assertFalse(form.template_id)  # no template

        form.template_id = partner_tmpl
        composer = form.save()
        self.assertEqual(composer.partner_cc_ids, expecting)
        self.assertEqual(composer.partner_bcc_ids, expecting)

    def set_company(self):
        company = self.env.company
        # Company default values
        company.default_partner_cc_ids = self.partner_cc3
        company.default_partner_bcc_ids = self.partner_cc2

    def test_recipient_ids_and_cc_bcc(self):
        self.set_company()
        form = self.open_mail_composer_form()
        composer = form.save()
        composer.partner_ids = self.partner + self.partner_cc

        with self.mock_mail_gateway():
            composer._action_send_mail()

        message = self.test_record.message_ids[0]
        self.assertEqual(len(message.mail_ids), 1)

        # Only 4 partners notified
        self.assertEqual(len(message.notified_partner_ids), 4)
        self.assertEqual(len(message.notification_ids), 4)

    def test_mail_without_cc_bcc(self):
        self.set_company()
        form = self.open_mail_composer_form()
        subject = "Testing without cc/bcc single mail"
        form.subject = subject
        composer = form.save()
        composer.partner_cc_ids = None
        composer.partner_bcc_ids = None
        composer.partner_ids = self.partner + self.partner_cc  # 2 emails are sent
        ctx = {"mail_notify_force_send": True}
        ctx.update(composer.env.context)
        composer = composer.with_context(**ctx)
        with self.mock_mail_gateway():
            composer._action_send_mail()
        sent_mails = 0
        for mail in self._mails:
            if subject == mail.get("subject"):
                sent_mails += 1
        self.assertEqual(sent_mails, 2, "There should be 2 mails sent")


@tagged("-at_install", "post_install")
class TestMailComposerCcBccWithTracking(MailCase, MailComposerCcBccMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_mail_composer_cc_bcc_data()
        cls.admin_user = cls.env.ref("base.user_admin")

        if "purchase.order" in cls.env:
            cls.new_po = (
                cls.env["purchase.order"]
                .create(
                    {
                        "partner_id": cls.partner.id,
                    }
                )
                .with_context(mail_notrack=False)
            )

    def test_tracking_mail_without_cc_bcc(self):
        if "purchase.order" in self.env:
            self.cr.precommit.clear()
            # create a PO
            # user subscribe to tracking status of PO
            self.new_po.message_subscribe(
                partner_ids=self.admin_user.partner_id.ids,
                subtype_ids=(
                    (
                        self.env.ref("purchase.mt_rfq_sent")
                        | self.env.ref("purchase.mt_rfq_confirmed")
                    ).ids
                ),
            )

            composer_ctx = self.new_po.action_rfq_send()
            # send RFQ with cc/bcc
            form = Form(
                self.env["mail.compose.message"].with_context(**composer_ctx["context"])
            )
            composer = form.save()
            composer.partner_ids = self.partner
            composer.partner_cc_ids = self.partner_cc
            composer.partner_bcc_ids = self.partner_bcc

            with self.mock_mail_gateway(), self.mock_mail_app():
                composer._action_send_mail()
                self.flush_tracking()
            self.assertEqual(
                len(self._new_msgs),
                2,
                "Expected a tracking message and a RFQ message",
            )
            self.assertEqual(
                self.ref("purchase.mt_rfq_sent"),
                self._new_msgs[1].subtype_id.id,
                "Expected a tracking message",
            )

            # RFQ email should include cc/bcc
            rfq_message = self._new_msgs.filtered(lambda x: x.message_type == "comment")
            self.assertEqual(len(rfq_message.notified_partner_ids), 3)
            self.assertEqual(len(rfq_message.notification_ids), 3)
            rfq_mail = rfq_message.mail_ids
            self.assertEqual(len(rfq_mail.recipient_ids), 3)

            # tracking email should not include cc/bcc
            tracking_message = self._new_msgs.filtered(
                lambda x: x.message_type == "notification"
            )
            tracking_field_mail = tracking_message.mail_ids
            self.assertEqual(len(tracking_field_mail.recipient_ids), 1)
            self.assertEqual(
                tracking_field_mail.recipient_ids, self.admin_user.partner_id
            )
