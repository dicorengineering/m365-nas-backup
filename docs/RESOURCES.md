# Resource use on smaller NAS hardware

The app uses **one Python service and an embedded SQLite catalog**, with no database server,
search engine or queue container. Mailboxes and operations run serially. One message is exported
per request so a batch of large attachments cannot be held in RAM at once. This trades some
throughput for smaller memory spikes.

## Defaults

| Setting in compose.yaml | Default | Purpose |
| --- | --- | --- |
| mem_limit | 512m | 512 MiB maximum container memory, allocated as used |
| memswap_limit | 512m | Same as memory limit; no container swap when supported by the host |
| cpus | 1.0 | At most one CPU's worth of processing across the host's cores |
| pids_limit | 64 | Bounds process/thread count |
| /tmp tmpfs | 32m | Small temporary filesystem ceiling |
| log rotation | 3 x 5m | Bounds Docker's service logs |
| health probe | 60 seconds | Checks service liveness; Kuma checks backup freshness separately |

The limits are ceilings, not reservations. Docker/Container Station, QTS and other apps need
their own memory. Removing the QPKG wrapper simplifies installation; it does not remove the
container runtime's overhead. No image compilation is performed on the NAS.

## What is measured

Each package includes `resource-report.json` from its Linux CI run. It records:
- Idle web service resident memory (RSS) and Docker's memory reading.
- Peak RSS for the synthetic backup process alongside the running web service.
- Whole-container peak including filesystem cache and any out-of-memory kills.
- Image size and the applied CPU/memory limits.

The synthetic test performs a baseline of 2,000 items at 64 KiB and two at 16 MiB, an incremental
change/deletion, and verification of both retained snapshots. It exercises the real Graph
JSON/base64 decoding, encryption, compression, disk writes and delta handling using generated
responses. Generating those responses also uses test-process RAM. There are no tenant credentials.

These are **CI measurements**, not TS-453A measurements or a promise for every mailbox.
The report's runtime is not a predicted NAS backup time.

## Practical limits and tuning

Full mailbox manifests are held in memory. Large item counts, unusually large messages and
simultaneous console browsing can need more RAM than the synthetic workload. Single-message
export still requires encoded/decoded buffers. The 512 MiB ceiling is a starting point, not
an established maximum mailbox size.

Watch Container Station during the first baseline and verification. Use a backup schedule that
leaves time for the NAS to finish. A slower first baseline is expected with one-message exports.
If the container is repeatedly killed with an out-of-memory indication, pause scheduling,
inspect logs/state, and raise **both** `mem_limit` and `memswap_limit` to `768m` or `1g`
only if the NAS has headroom. Recreate the application keeping the same volumes. If the host
does not support swap accounting, Docker may warn that the swap ceiling cannot be enforced.

An interrupted run never publishes a completed point; after restart it is marked failed.
Check /backup-status and the retained points before resuming. Do not lower memory in the middle
of a backup or restore. A CPU cap of `0.5` can reduce load further at the cost of runtime;
adjust the overdue threshold accordingly. Do not add worker replicas.

Definitions: [Compose service resource settings](https://docs.docker.com/reference/compose-file/services/).
