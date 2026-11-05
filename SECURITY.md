# Security policy

This experimental project has no independent security certification or guaranteed
response time. Only the newest published alpha is a candidate for fixes; no version
is promised to receive long-term maintenance.

Report vulnerabilities through [GitHub private vulnerability reporting](https://github.com/dicorengineering/m365-nas-backup/security/advisories/new).
Do not post exploit details, live credentials, tenant data, messages or backup files
in public issues. If private reporting is unavailable, open a public issue asking for
a private contact channel without disclosing the vulnerability or sensitive data.

Provide the affected version, source location, expected boundary, observed effect,
and a minimal reproduction with synthetic data. Limit testing to systems you own or
are explicitly authorized to test. Do not test availability or restore behavior
against a production mailbox.

Protect configuration/encryption keys and all NAS volumes. The SQLite operational
catalog has unencrypted identifiers and restore plans. Generated EML ZIP exports
contain unencrypted mail. Authentication does not make direct HTTP safe on an
untrusted network; use a protected network or HTTPS.
