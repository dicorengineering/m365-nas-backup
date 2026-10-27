"""Publish the CI-tested image privately and verify a real registry pull."""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    repository = os.environ["GITHUB_REPOSITORY"]
    owner, package = repository.lower().split("/")
    token = os.environ["GH_TOKEN"]
    image = "ghcr.io/" + repository.lower() + ":0.1.0-alpha.3"
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

    def docker(*args):
        return subprocess.check_output(["docker", *args], text=True).strip()

    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("Publish only from main")
    if not api("/repos/" + repository)["private"]:
        raise RuntimeError("Repository must remain private")
    existing = api(package_path, missing=True)
    if existing and existing["visibility"] != "private":
        raise RuntimeError("Refusing to push to a non-private package")
    image_id = docker("image", "inspect", "--format", "{{.Id}}", image)
    try:
        subprocess.run(
            ["docker", "login", "ghcr.io", "-u", os.environ["GITHUB_ACTOR"], "--password-stdin"],
            input=token,
            text=True,
            check=True,
        )
        subprocess.run(["docker", "push", image], check=True)
        metadata = None
        for _ in range(10):
            metadata = api(package_path, missing=True)
            if metadata:
                break
            time.sleep(2)
        if not metadata or metadata["visibility"] != "private":
            raise RuntimeError("Could not verify private package visibility")
        if metadata.get("repository", {}).get("full_name", "").lower() != repository.lower():
            raise RuntimeError("Package is not linked to the intended private repository")
        docker("image", "rm", image)
        subprocess.run(["docker", "pull", image], check=True)
        assert docker("image", "inspect", "--format", "{{.Id}}", image) == image_id
        report = {
            "image": image,
            "image_id": image_id,
            "visibility": metadata["visibility"],
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
