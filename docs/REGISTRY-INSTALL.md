# Install by pulling the private Docker image

This is the preferred installation method for QNAP Container Station. It avoids the image
archive importer. The GitHub repository and container package remain private.

## One-time access setup

1. Sign into GitHub using an account with access to dicorengineering/m365-nas-backup.
2. Open [new classic token](https://github.com/settings/tokens/new?scopes=read:packages&description=M365%20NAS%20read-only%20pull).
3. Give the token an expiry and select **read:packages** only. Do not grant write/delete access.
   GitHub's registry requires a **classic** token, not a fine-grained token.
4. In an administrator SSH session on the NAS, run:

   ```sh
   docker login ghcr.io -u YOUR_GITHUB_USERNAME
   ```

   For Matt's owning account, the username is `dicorengineering`. At the Password prompt,
   paste the token (not your GitHub account password). Never paste the token into this chat.
   The NAS stores registry credentials for that NAS user; protect its home directory.
   Replace the token/login when it expires.

## Pull and confirm

```sh
docker pull ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.5
docker image inspect ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.5 --format '{{.Id}} {{.Architecture}} {{.Os}}'
```

The inspection should show an image ID followed by `amd64 linux`.
Refresh **Container Station → Images**, clearing any search/filter.

## Start the app

Open the repository's [compose.yaml](../compose.yaml), copy its full contents, then use
**Container Station → Applications → Create** and paste them. The image line must be:

```yaml
image: ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.5
```

Since the image is already pulled, leave forced pulling disabled. A login in your SSH account
may not be shared with Container Station's own registry manager. For pulls through the GUI,
add a registry there with URL `ghcr.io`, your GitHub username and the same read-only token.

Or save compose.yaml on the NAS and, from its directory, run `docker compose up -d --pull never`.

Continue with [console access](QNAP-INSTALL.md#5-open-the-console-and-sign-in),
[Microsoft setup](MICROSOFT-SETUP.md), [usage/Kuma](USAGE.md), and [recovery](RECOVERY.md).
Default limits remain 512 MiB and one CPU. Existing volume names and encryption keys must be preserved.

For upgrades, back up configuration and a verified recovery bundle, pull the intended new tag,
change the image tag in Compose and recreate the application keeping its volumes.
Do not use an automatic image updater during the alpha.

If login fails, check the username, classic token scope/expiry, and package access.
If pulling fails with access denied, sign in as an account allowed to read the private repository.
If it says manifest unknown, check the exact tag. The image is linux/amd64 only.

Reference: [GitHub Container Registry authentication](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
