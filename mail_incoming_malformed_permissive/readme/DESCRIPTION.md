Odoo truncates or rejects some incoming mails because they are malformed.
This module handles the following known cases:

- **Several `<html>` documents in one part**: some mail clients glue several
  `<html>` documents together. Odoo keeps only the first one and drops the rest
  of the body. This module keeps every document.
