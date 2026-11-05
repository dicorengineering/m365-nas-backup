"""Publish the tested image and record authenticated/anonymous pull verification."""

import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    repository = os.environ["GITHUB_REPOSITORY"]
    owner, package = repository.lower().split("/")
    token = os.environ["GH_TOKEN"]
    image = next(
        line.split("image:", 1)[1].strip()
        for line in Path("compose.yaml").read_text().splitlines()
        if "image:" in line
    )
    package_path = f"/users/{owner}/packages/container/{package}"

    def api(path, missing=False):
        request = urllib.request.Request(
            "https://api.github.com" + path,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if missing and error.code == 404:
                return None
            raise RuntimeError(f"GitHub metadata check failed: HTTP {error.code}") from None

    def docker(*args, env=None):
        return subprocess.check_output(["docker", *args], text=True, env=env).strip()

    if (
        repository.lower() != "dicorengineering/m365-nas-backup"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
    ):
        raise RuntimeError("Publish only from the upstream main branch")
    if api("/repos/" + repository)["private"]:
        raise RuntimeError("Public release requires the owner's repository publication first")
    image_id = docker("image", "inspect", "--format", "{{.Id}}", image)
    try:
        subprocess.run(
            ["docker", "login", "ghcr.io", "-u", os.environ["GITHUB_ACTOR"], "--password-stdin"],
            input=token,
            text=True,
            check=True,
        )
        # Immutable version tags: a rerun must not silently replace a delivered image.
        existing = subprocess.run(["docker", "manifest", "inspect", image], capture_output=True)
        if existing.returncode == 0:
            raise RuntimeError("Tag already exists; do not overwrite a published release")
        if (
            b"manifest unknown" not in existing.stderr.lower()
            and b"no such manifest" not in existing.stderr.lower()
        ):
            raise RuntimeError("Could not establish that the version tag is unused")
        subprocess.run(["docker", "push", image], check=True)
        metadata = None
        for _ in range(10):
            metadata = api(package_path, missing=True)
            if metadata:
                break
            time.sleep(2)
        if not metadata:
            raise RuntimeError("Could not verify package metadata")
        linked_repository = (metadata.get("repository") or {}).get("full_name", "")
        if linked_repository and linked_repository.lower() != repository.lower():
            raise RuntimeError("Package is linked to a different repository")
        docker("image", "rm", image)
        subprocess.run(["docker", "pull", image], check=True)
        if docker("image", "inspect", "--format", "{{.Id}}", image) != image_id:
            raise RuntimeError("Pulled image differs from the tested image")
        anonymous = False
        if metadata["visibility"] == "public":
            with tempfile.TemporaryDirectory() as config:
                clean_env = {**os.environ, "DOCKER_CONFIG": config}
                subprocess.run(["docker", "pull", image], env=clean_env, check=True)
                if docker("image", "inspect", "--format", "{{.Id}}", image) != image_id:
                    raise RuntimeError("Anonymous pull differs from the tested image")
                anonymous = True
        else:
            print("Package visibility still requires owner action; public offline download is available.")
        report = {
            "image": image,
            "image_id": image_id,
            "visibility": metadata["visibility"],
            "anonymous_pull_verified": anonymous,
            "linked_repository": linked_repository or None,
            "package_url": metadata["html_url"],
            "source_commit": os.environ["GITHUB_SHA"],
            "pulled_image_matches_tested_image": True,
            "repo_digests": json.loads(
                docker("image", "inspect", "--format", "{{json .RepoDigests}}", image)
            ),
        }
        Path("build/registry-report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        subprocess.run(["docker", "logout", "ghcr.io"], check=False)


if __name__ == "__main__":
    main()
