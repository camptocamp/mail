Odoo native does not support defining a Cc field in the Mail Composer by
default; instead, it only has a unique Recipients fields, which is
confusing for a lot of end users.

This module allows to properly separate To:, Cc:, and Bcc: fields in the
Mail Composer.

From Odoo 17.0, this module sends one mail per recipient and keeps same all headers (To, Cc, Bcc) in all emails

## Features

- Add Cc and Bcc fields to company form to use them as default in mail
  composer form.
- Add Bcc field to mail template form. Use Cc and Bcc fields to lookup
  partners by email then add them to corresponding fields in mail
  composer form.

## Scope

This module extends the **Mail Composer** flow: the Cc / Bcc recipients it
adds are taken into account when the email goes through
`mail.compose.message` (the *Send message* wizard, e.g. sending a sale
order).

Flows that build their emails from a template without the composer are **not**
covered — invoice sending is the main one, since `account.move.send` calls
`message_post()` directly (core even notes there that it should "use standard
composer / template code to be sure it is aligned with standard recipients
management"). Supporting Bcc there would mean carrying the template value
through the standard `mail.template` → `mail.mail` generation, which is a
separate feature rather than part of this module: `mail_composer_cc_bcc_account`
covers the invoice flow.
