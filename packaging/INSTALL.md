# M365 NAS Backup — Docker installation

Prefer [private registry pull](docs/REGISTRY-INSTALL.md) to avoid the archive importer.

For offline use, start with [QNAP installation](docs/QNAP-INSTALL.md) or
[Linux Docker installation](docs/DOCKER-INSTALL.md).

The image archive is prebuilt. Import it, then use the supplied compose.yaml.
The old QPKG installer has been retired.

Read [resource use](docs/RESOURCES.md), [Microsoft setup](docs/MICROSOFT-SETUP.md),
[usage and Uptime Kuma](docs/USAGE.md), [recovery](docs/RECOVERY.md), and
[acceptance checks](docs/ACCEPTANCE.md).

SHA256SUMS covers the supplied files. SOURCE-COMMIT.txt identifies the source revision;
resource-report.json contains that build's synthetic test measurements.
import-report.json records the archive format and fresh import/startup checks.
The archive uses the classic Docker format for NAS importer compatibility.

This is a private development alpha. Physical NAS and live Microsoft acceptance remain required.
