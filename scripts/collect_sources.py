"""Publish exact upstream source archives alongside a distributable container.

Downloads archives as data; never executes or extracts upstream build scripts.
The Debian archive API identifies exact source versions even after mirror rotation.
"""

import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import tarfile
import time
import tomllib
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path("build/dependency-sources")
INDEX = []


def fetch(url, target=None, algorithm="sha256", expected=None):
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "m365-nas-backup-source-bundle/1"})
            with urllib.request.urlopen(request, timeout=120) as response:
                if target is None:
                    return response.read()
                target.parent.mkdir(parents=True, exist_ok=True)
                digest, sha256 = hashlib.new(algorithm), hashlib.sha256()
                with target.open("wb") as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                        digest.update(chunk)
                        sha256.update(chunk)
                if expected and digest.hexdigest() != expected:
                    raise ValueError("Upstream source checksum mismatch")
                return {
                    "path": target.relative_to(ROOT).as_posix(),
                    "url": url,
                    "sha256": sha256.hexdigest(),
                    "upstream_checksum": expected,
                }
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2**attempt)


def api(url):
    return json.loads(fetch(url))


def debian_mirror_sources(image, pairs):
    """Use APT's signed source indexes first; snapshot is the exact-version fallback."""
    code = """
import json, subprocess
from pathlib import Path
for p in Path('/etc/apt/sources.list.d').glob('*.sources'):
    p.write_text(p.read_text().replace('Types: deb\\n', 'Types: deb deb-src\\n'))
subprocess.run(['apt-get', 'update', '-qq'], check=True)
pairs=json.loads(Path('/sources/debian-request.json').read_text())
results=[]
for name, version in pairs:
    directory=Path('/sources/debian') / name
    directory.mkdir(parents=True, exist_ok=True)
    completed=subprocess.run(
        ['apt-get', 'source', '--download-only', '--only-source', name+'='+version],
        cwd=directory, capture_output=True, text=True)
    print('Debian mirror source: '+name+' '+('downloaded' if completed.returncode==0 else 'use archive'), flush=True)
    if completed.returncode==0:
        results.append([name, version])
Path('/sources/debian-mirror.json').write_text(json.dumps(results))
"""
    (ROOT / "debian-request.json").write_text(json.dumps(pairs))
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            "0",
            "--entrypoint",
            "python",
            "--volume",
            str(ROOT.resolve()) + ":/sources",
            image,
            "-c",
            code,
        ],
        check=True,
    )
    completed = {tuple(pair) for pair in json.loads((ROOT / "debian-mirror.json").read_text())}
    for name, version in sorted(completed):
        for path in sorted((ROOT / "debian" / name).iterdir()):
            if path.is_file():
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                INDEX.append(
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "package": name,
                        "version": version,
                        "ecosystem": "debian",
                        "sha256": digest,
                        "verification": "APT verified signed Debian source index and exact source version",
                    }
                )
    return [pair for pair in pairs if pair not in completed]


def debian_source(pair):
    name, version = pair
    url = (
        "https://snapshot.debian.org/mr/package/"
        + quote(name, safe="")
        + "/"
        + quote(version, safe="")
        + "/srcfiles"
    )
    print("Debian archive source: " + name + " " + version, flush=True)
    hashes = api(url)["result"]
    if not hashes:
        raise ValueError("Missing Debian source: " + name + " " + version)
    records = []
    for entry in hashes:
        digest = entry["hash"]
        if not re.fullmatch(r"[a-f0-9]{40}", digest):
            raise ValueError("Unexpected Debian archive digest")
        metadata = api("https://snapshot.debian.org/mr/file/" + digest + "/info")["result"]
        filename = metadata[0]["name"]
        if Path(filename).name != filename or filename in (".", ".."):
            raise ValueError("Unexpected source archive filename")
        record = fetch(
            "https://snapshot.debian.org/file/" + digest, ROOT / "debian" / name / filename, "sha1", digest
        )
        records.append({**record, "package": name, "version": version, "ecosystem": "debian"})
    return records


def python_source(package):
    name, version = package["name"], package["version"]
    if name == "m365-nas-backup":
        return []
    files = api(f"https://pypi.org/pypi/{quote(name)}/{quote(version)}/json")["urls"]
    source = next((f for f in files if f["packagetype"] == "sdist"), None)
    if source is None:
        raise ValueError("Missing Python source distribution: " + name)
    filename = source["filename"]
    if Path(filename).name != filename:
        raise ValueError("Unexpected Python source filename")
    record = fetch(source["url"], ROOT / "python" / filename, expected=source["digests"]["sha256"])
    return [{**record, "package": name, "version": version, "ecosystem": "pypi"}]


def rust_sources():
    crates = {}
    for archive in (ROOT / "python").glob("*.tar.gz"):
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                if member.name.endswith("/Cargo.lock") and member.size < 10_000_000:
                    lock = tomllib.loads(tar.extractfile(member).read().decode())
                    for package in lock.get("package", []):
                        if package.get("source", "").startswith("registry+") and package.get("checksum"):
                            crates[(package["name"], package["version"])] = package["checksum"]
    for (name, version), checksum in sorted(crates.items()):
        url = f"https://static.crates.io/crates/{quote(name)}/{quote(name)}-{quote(version)}.crate"
        record = fetch(url, ROOT / "rust" / (name + "-" + version + ".crate"), expected=checksum)
        INDEX.append({**record, "package": name, "version": version, "ecosystem": "cargo"})


def main():
    image = next(
        line.split("image:", 1)[1].strip()
        for line in Path("compose.yaml").read_text().splitlines()
        if "image:" in line
    )
    tag = image.rsplit(":", 1)[1]
    ROOT.mkdir(parents=True, exist_ok=True)
    container = subprocess.check_output(["docker", "create", image], text=True).strip()
    try:
        subprocess.run(
            ["docker", "cp", container + ":/usr/share/m365-nas-backup/licenses", str(ROOT / "notices")],
            check=True,
        )
    finally:
        subprocess.run(["docker", "rm", container], check=True, stdout=subprocess.DEVNULL)
    inventory = json.loads((ROOT / "notices/inventory.json").read_text())
    pairs = sorted({(p["source"], p["source_version"]) for p in inventory["debian_packages"]})
    pairs = debian_mirror_sources(image, pairs)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for records in pool.map(debian_source, pairs):
            INDEX.extend(records)
            print("Collected Debian source: " + records[0]["package"], flush=True)
        for records in pool.map(python_source, inventory["python_packages"]):
            INDEX.extend(records)
            if records:
                print("Collected Python source: " + records[0]["package"], flush=True)
    env = json.loads(
        subprocess.check_output(
            ["docker", "image", "inspect", "--format", "{{json .Config.Env}}", image], text=True
        )
    )
    values = dict(entry.split("=", 1) for entry in env)
    version = values["PYTHON_VERSION"]
    INDEX.append(
        fetch(
            f"https://www.python.org/ftp/python/{version}/Python-{version}.tar.xz",
            ROOT / ("Python-" + version + ".tar.xz"),
            expected=values["PYTHON_SHA256"],
        )
    )
    # Include the embedded OpenSSL sources, not just the system OpenSSL package.
    code = "from cryptography.hazmat.backends.openssl.backend import backend; print(backend.openssl_version_text())"
    openssl = subprocess.check_output(
        ["docker", "run", "--rm", "--entrypoint", "python", image, "-c", code], text=True
    ).split()[1]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+[a-z]?", openssl):
        raise ValueError("Unexpected bundled OpenSSL version")
    INDEX.append(
        fetch(
            f"https://github.com/openssl/openssl/releases/download/openssl-{openssl}/openssl-{openssl}.tar.gz",
            ROOT / ("openssl-" + openssl + ".tar.gz"),
        )
    )
    recipe_sha = api(
        "https://api.github.com/repos/docker-library/python/commits?path=3.13/slim-bookworm/Dockerfile&per_page=1"
    )[0]["sha"]
    if not re.fullmatch(r"[a-f0-9]{40}", recipe_sha):
        raise ValueError("Invalid upstream recipe revision")
    recipe_url = (
        f"https://raw.githubusercontent.com/docker-library/python/{recipe_sha}/3.13/slim-bookworm/Dockerfile"
    )
    recipe = fetch(recipe_url, ROOT / "upstream-python.Dockerfile")
    recipe["revision"] = recipe_sha
    recipe["python_version_matches_image"] = ("ENV PYTHON_VERSION " + version) in (
        ROOT / "upstream-python.Dockerfile"
    ).read_text()
    INDEX.append(recipe)
    INDEX.append(
        fetch(
            f"https://raw.githubusercontent.com/docker-library/python/{recipe_sha}/LICENSE",
            ROOT / "upstream-python-LICENSE",
        )
    )
    rust_sources()
    for name in ("Dockerfile", "requirements.txt", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        (ROOT / name).write_bytes(Path(name).read_bytes())
    subprocess.run(
        [
            "git",
            "archive",
            "--format=tar.gz",
            "--output=" + str(ROOT / "application-source.tar.gz"),
            os.environ["GITHUB_SHA"],
        ],
        check=True,
    )
    (ROOT / "SOURCE-INDEX.json").write_text(json.dumps(INDEX, indent=2) + "\n")
    (ROOT / "README.txt").write_text(
        "Exact upstream sources and notices for " + image + "\n"
        "Each component retains its own license. Archives have not been modified.\n"
        "Debian .dsc/orig/debian archives include package build instructions.\n"
        "Python source archives include their build metadata; Rust crate sources are included\n"
        "where locked in those distributions. Application recipe/source is included.\n"
        "Source URLs and checksums are in SOURCE-INDEX.json.\n"
    )
    Path("dist").mkdir(exist_ok=True)
    source_bundle = Path("dist") / ("m365-nas-backup-" + tag + "-dependency-sources.tar")
    with tarfile.open(source_bundle, "w") as output:
        output.add(ROOT, arcname="dependency-sources")
    with tarfile.open(Path("dist") / ("m365-nas-backup-" + tag + "-notices.tar.gz"), "w:gz") as output:
        output.add(ROOT / "notices", arcname="notices")
    print(
        json.dumps(
            {
                "source_archives": len(INDEX),
                "bundle": str(source_bundle),
                "bytes": source_bundle.stat().st_size,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
