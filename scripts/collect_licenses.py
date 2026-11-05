"""Collect installed distribution notices without importing application/dependency code."""

import argparse
import hashlib
import importlib.metadata
import json
import re
import shutil
import subprocess
from pathlib import Path


def collect(destination, requirements=None):
    destination.mkdir(parents=True, exist_ok=True)
    if requirements:
        distributions = []
        for line in requirements.read_text().splitlines():
            if "==" in line and not line.startswith("#"):
                name, version = line.split("==")
                dist = importlib.metadata.distribution(name)
                if dist.version != version:
                    raise ValueError("Installed dependency version differs from requirements: " + name)
                distributions.append(dist)
    else:
        distributions = list(importlib.metadata.distributions())
    packages = []
    for dist in sorted(distributions, key=lambda d: d.metadata["Name"].lower()):
        name = re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower()
        copied = []
        for entry in dist.files or []:
            path = Path(str(entry))
            if path.is_absolute() or ".." in path.parts:
                continue
            if not re.match(r"^(LICENSE|COPYING|NOTICE|AUTHORS)([.\-_]|$)", path.name, re.I):
                continue
            source = Path(dist.locate_file(entry))
            if not source.is_file():
                continue
            target = destination / name / path
            target.parent.mkdir(parents=True, exist_ok=True)
            content = source.read_bytes()
            target.write_bytes(content)
            copied.append(
                {
                    "path": str(target.relative_to(destination)).replace("\\", "/"),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
        if not copied:
            raise ValueError("No upstream license files found for " + name)
        packages.append(
            {
                "name": name,
                "version": dist.version,
                "license": dist.metadata.get("License-Expression") or dist.metadata.get("License"),
                "project_urls": dist.metadata.get_all("Project-URL") or [],
                "home_page": dist.metadata.get("Home-page"),
                "license_files": copied,
            }
        )
    inventory = {"python_packages": packages}
    if Path("/var/lib/dpkg/status").exists():
        rows = subprocess.check_output(
            ["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\n"],
            text=True,
        ).splitlines()
        inventory["debian_packages"] = [
            dict(zip(("name", "version", "source", "source_version"), row.split("\t"), strict=True))
            for row in rows
        ]
        for p in Path("/usr/share/doc").glob("*/copyright"):
            target = destination / "debian" / p.parent.name / "copyright"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)
        shutil.copytree("/usr/share/common-licenses", destination / "common-licenses", dirs_exist_ok=True)
    for path in Path("/usr/local/lib").glob("python*/LICENSE.txt"):
        shutil.copyfile(path, destination / "CPython-LICENSE.txt")
    output = destination.parent / "python-packages.json" if requirements else destination / "inventory.json"
    output.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Collected notices for {len(packages)} installed Python distributions")
    return inventory


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requirements", type=Path)
    options = parser.parse_args()
    collect(options.output, options.requirements)
