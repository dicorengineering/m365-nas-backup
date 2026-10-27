"""Export a classic Docker archive and test importing that exact file.

CI only: an ephemeral, privileged Docker-in-Docker daemon provides the classic
image store. This helper is never shipped in the NAS image or run on a real NAS.
"""

import gzip
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
from pathlib import Path
from uuid import uuid4

COMPAT_ENGINE = "docker:27.1.2-dind"


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def validate_archive(path, image, image_id):
    with tarfile.open(path) as archive:
        names = set(archive.getnames())
        if "oci-layout" in names or "index.json" in names:
            raise ValueError("Expected a classic Docker archive, not an OCI layout")
        manifest = json.load(archive.extractfile("manifest.json"))
        assert len(manifest) == 1 and manifest[0]["RepoTags"] == [image]
        entry = manifest[0]
        assert entry["Config"] == image_id.removeprefix("sha256:") + ".json"
        raw_config = archive.extractfile(entry["Config"]).read()
        assert "sha256:" + hashlib.sha256(raw_config).hexdigest() == image_id
        config = json.loads(raw_config)
        assert config["architecture"] == "amd64" and config["os"] == "linux"
        assert config["config"]["User"] == "10001:10001"
        assert len(entry["Layers"]) == len(config["rootfs"]["diff_ids"])
        for name, digest in zip(entry["Layers"], config["rootfs"]["diff_ids"], strict=True):
            assert name.endswith("/layer.tar")
            folder = name.rsplit("/", 1)[0]
            assert folder + "/json" in names and folder + "/VERSION" in names
            with archive.extractfile(name) as stream:
                assert "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest() == digest
        repositories = json.load(archive.extractfile("repositories"))
        repository, tag = image.rsplit(":", 1)
        assert repositories[repository][tag] == entry["Layers"][-1].split("/")[0]
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Run this packaging helper only on an isolated GitHub Actions runner")
    root = Path(__file__).resolve().parents[1]
    spec = json.loads(docker("compose", "-f", str(root / "compose.yaml"), "config", "--format", "json"))
    image = spec["services"]["backup"]["image"]
    version = image.rsplit(":", 1)[1]
    image_id = docker("image", "inspect", "--format", "{{.Id}}", image)
    staging = root / "build"
    output = root / "dist"
    staging.mkdir(exist_ok=True)
    output.mkdir(exist_ok=True)
    incoming = staging / "source-image.tar"
    destination = output / f"m365-nas-backup-{version}-amd64.tar.gz"
    docker("save", "--output", str(incoming), image)
    daemon = "mnb-packager-" + uuid4().hex[:10]
    remote = ("exec", daemon, "docker")
    try:
        docker(
            "run",
            "-d",
            "--privileged",
            "--name",
            daemon,
            "-e",
            "DOCKER_TLS_CERTDIR=",
            COMPAT_ENGINE,
            "--storage-driver=vfs",
        )
        for _ in range(60):
            ready = subprocess.run(["docker", *remote, "info"], capture_output=True, check=False)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Compatibility daemon did not start")
        version = docker(*remote, "version", "--format", "{{.Server.Version}}")
        with incoming.open("rb") as source:
            subprocess.run(["docker", "exec", "-i", daemon, "docker", "load"], stdin=source, check=True)
        assert docker(*remote, "image", "inspect", "--format", "{{.Id}}", image) == image_id
        # Let Docker's classic store create the compatibility layout; don't hand-edit layers.
        with gzip.open(destination, "wb", compresslevel=1) as target:
            with subprocess.Popen(["docker", *remote, "save", image], stdout=subprocess.PIPE) as process:
                shutil.copyfileobj(process.stdout, target)
                if process.wait() != 0:
                    raise RuntimeError("Classic image export failed")
        checksum = validate_archive(destination, image, image_id)
        # Remove the image, then import the exact compressed file we will distribute.
        docker(*remote, "image", "rm", image)
        missing = subprocess.run(
            ["docker", *remote, "image", "inspect", image], capture_output=True, check=False
        )
        assert missing.returncode != 0
        with destination.open("rb") as source:
            subprocess.run(["docker", "exec", "-i", daemon, "docker", "load"], stdin=source, check=True)
        assert docker(*remote, "image", "inspect", "--format", "{{.Id}}", image) == image_id
        assert image in docker(*remote, "image", "ls", "--format", "{{.Repository}}:{{.Tag}}").splitlines()
        docker(
            *remote,
            "run",
            "-d",
            "--name",
            "import-check",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "512m",
            "--memory-swap",
            "512m",
            "--cpus",
            "1",
            "--tmpfs",
            "/config:uid=10001,gid=10001,mode=700,size=16m",
            "--tmpfs",
            "/data:uid=10001,gid=10001,mode=700,size=32m",
            "--tmpfs",
            "/exports:uid=10001,gid=10001,mode=700,size=16m",
            "--tmpfs",
            "/tmp:mode=1777,size=32m",
            image,
        )
        probe = [
            "docker",
            *remote,
            "exec",
            "import-check",
            "python",
            "-c",
            "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=2).status == 200",
        ]
        for _ in range(60):
            if subprocess.run(probe, capture_output=True, check=False).returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Imported image failed its isolated health check")
        # The modern-engine Compose/resource test must also start from the shipped archive.
        docker("image", "rm", image)
        docker("load", "--input", str(destination))
        assert docker("image", "inspect", "--format", "{{.Id}}", image) == image_id
        report = {
            "image": image,
            "image_id": image_id,
            "archive": destination.name,
            "archive_sha256": checksum,
            "format": "classic Docker save",
            "compatibility_engine": version,
            "fresh_import_listed": True,
            "imported_container_health": 200,
            "config_and_all_layer_hashes_verified": True,
            "modern_engine_loaded_same_archive": True,
            "limitations": "Engine import tests do not exercise QNAP's proprietary Container Station UI.",
        }
        (staging / "import-report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    except Exception:
        subprocess.run(["docker", "logs", "--tail", "80", daemon], check=False)
        subprocess.run(["docker", *remote, "logs", "--tail", "80", "import-check"], check=False)
        raise
    finally:
        subprocess.run(["docker", "rm", "-fv", daemon], capture_output=True, check=False)
        incoming.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
