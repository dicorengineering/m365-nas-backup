# AI development, experimental status and responsibility

This application was developed using OpenAI Codex and AI-generated code.
It is experimental alpha software. AI-generated code can contain mistakes,
security vulnerabilities and incorrect assumptions, even when tests pass.

Automated tests use synthetic mail and mocked Microsoft responses. They do not
establish complete Exchange restore fidelity, compatibility with every tenant,
physical QNAP reliability, or suitability for regulatory/compliance obligations.
There has been no independent professional security audit or certification.

Backups, retention cleanup and restoration can fail, omit information or cause
data loss, duplication or corruption. Validate backup and restore behavior with
disposable mail in your own environment before relying on it. Keep an independent,
verified backup and protect the original encryption key. No recovery guarantee,
support service level or maintenance commitment is provided.

Review the supported scope in the README and the acceptance guide. This project
currently covers selected primary/shared Exchange email folders; it is not a
complete Microsoft 365 or tenant disaster-recovery product. Online archives and
other workloads/settings are excluded. Portable EML copies are not native PST
files and do not retain every Exchange-specific property.

You are responsible for authorizing mailbox access, complying with applicable
privacy/retention obligations and Microsoft service terms, managing credentials,
and securing the NAS and network. The application's software license does not
grant Microsoft 365, Outlook, QNAP, Docker service or other third-party licenses.

The MIT license supplies the project's legal warranty and liability terms.
The software is provided AS IS, without warranty; see [LICENSE](LICENSE).
This document explains operational limitations and adds no restrictions to MIT.

This is an independent community project. It is not affiliated with, endorsed by,
certified by or supported by Microsoft, QNAP, Docker or OpenAI. Product names and
trademarks belong to their respective owners. Descriptive use does not grant
trademark rights or imply endorsement.
