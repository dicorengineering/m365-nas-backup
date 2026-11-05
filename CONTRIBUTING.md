# Contributing

Please read [README](README.md), [DISCLAIMER](DISCLAIMER.md) and [AGENTS](AGENTS.md).
The project is an experimental, AI-developed application; changes need careful review.

For bug reports, include the app version, a sanitized error, expected/actual behavior,
and a reproduction using synthetic mail. Never attach real messages, backups,
encryption keys, certificates' private keys, tokens, session cookies or tenant secrets.
Use [private security reporting](SECURITY.md) for vulnerabilities.

Open a pull request with a focused explanation and relevant validation. Keep existing
completed snapshots readable and immutable, preserve failed-run delta checkpoints,
and never automatically retry an import with an uncertain result. Do not run tests
against someone else's mailbox, NAS or tenant.

Run pytest, Ruff, formatting checks and JavaScript syntax checks as described in the
README. Container/browser checks run in CI. Document changes to supported scope,
permissions, installation or recovery behavior. Use example.com and generated fixtures.

Disclose substantial AI assistance in the pull request and review generated code
yourself; generated output is not evidence of correctness. Check that any copied
third-party material permits redistribution and retain its required notices.

By submitting a contribution, you represent that you have the right to submit it
and agree to license your contribution under this project's MIT license.
Third-party code retains its own applicable license. No separate contributor
license agreement is required. No response or merge timeline is guaranteed.
