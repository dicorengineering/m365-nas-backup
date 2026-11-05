"""Bundle the tested installer and separate corresponding-source release assets."""

import hashlib
import os
import shutil
import zipfile
from pathlib import Path


def checksums(paths, root, destination):
    lines = []
    for path in sorted(paths):
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        lines.append(digest + "  " + path.relative_to(root).as_posix())
    destination.write_text("\n".join(lines) + "\n")


def main():
    dist = Path("dist")
    release = dist / "release"
    release.mkdir(parents=True, exist_ok=True)
    image = next(
        line.split("image:", 1)[1].strip()
        for line in Path("compose.yaml").read_text().splitlines()
        if "image:" in line
    )
    tag = image.rsplit(":", 1)[1]
    # Large source archives stay separate: installing the app needs no source/compiler.
    for suffix in ("dependency-sources.tar", "notices.tar.gz"):
        shutil.move(dist / ("m365-nas-backup-" + tag + "-" + suffix), release)
    shutil.copytree("docs", dist / "docs", dirs_exist_ok=True)
    shutil.copytree("third_party", dist / "third_party", dirs_exist_ok=True)
    for name in (
        "compose.yaml",
        "LICENSE",
        "DISCLAIMER.md",
        "THIRD_PARTY_NOTICES.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
    ):
        shutil.copyfile(name, dist / name)
    shutil.copyfile("packaging/INSTALL.md", dist / "INSTALL.md")
    for report in Path("build").glob("*-report.json"):
        shutil.copyfile(report, dist / report.name)
    (dist / "SOURCE-COMMIT.txt").write_text(os.environ["GITHUB_SHA"] + "\n")
    files = [
        p for p in dist.rglob("*") if p.is_file() and release not in p.parents and p.name != "SHA256SUMS"
    ]
    checksums(files, dist, dist / "SHA256SUMS")
    with zipfile.ZipFile(
        release / ("M365Backup-" + tag + "-docker-amd64.zip"),
        "w",
        compression=zipfile.ZIP_DEFLATED,
        allowZip64=True,
    ) as archive:
        for path in [*files, dist / "SHA256SUMS"]:
            archive.write(path, path.relative_to(dist).as_posix())
    checksums([p for p in release.iterdir() if p.is_file()], release, release / "RELEASE-SHA256SUMS")
    print("Prepared release assets: " + ", ".join(p.name for p in release.iterdir()))


if __name__ == "__main__":
    main()
