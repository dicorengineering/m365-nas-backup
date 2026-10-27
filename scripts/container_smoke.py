"""Exercise the shipped Compose on an isolated CI Docker engine, with fake data only."""

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def main():
    name = "mnb-test-" + uuid4().hex[:10]
    root = Path(__file__).resolve().parents[1]
    spec = json.loads(docker("compose", "-f", str(root / "compose.yaml"), "config", "--format", "json"))
    service = spec["services"]["backup"]
    image = service["image"]
    # Isolate names and host port. Keep all shipped resource/security/storage options.
    spec["name"] = name
    service["container_name"] = name
    service["ports"] = [{"target": 8765, "published": "0", "host_ip": "127.0.0.1", "protocol": "tcp"}]
    service["volumes"].append(
        {"type": "bind", "source": str(root / "scripts"), "target": "/smoke", "read_only": True}
    )
    for volume in spec["volumes"].values():
        volume["name"] = name + "-" + volume["name"]
    with TemporaryDirectory() as temporary:
        compose_file = Path(temporary) / "compose.json"
        compose_file.write_text(json.dumps(spec))
        compose = ("compose", "-p", name, "-f", str(compose_file))
        try:
            docker(*compose, "up", "-d", "--pull", "never")
            base = "http://" + docker(*compose, "port", "backup", "8765")

            def request(path, token="", body=None):
                headers = {"Authorization": "Bearer " + token}
                if body is not None:
                    headers["Content-Type"] = "application/json"
                req = urllib.request.Request(
                    base + path,
                    headers=headers,
                    data=json.dumps(body).encode() if body is not None else None,
                    method="PUT" if body is not None else "GET",
                )
                try:
                    with urllib.request.urlopen(req, timeout=5) as response:
                        return response.status, json.load(response)
                except urllib.error.HTTPError as response:
                    return response.code, json.load(response)

            def wait_ready():
                for _ in range(60):
                    try:
                        if request("/health")[0] == 200:
                            return
                    except (OSError, ValueError):
                        pass
                    time.sleep(1)
                raise RuntimeError("Container did not start")

            wait_ready()
            inspect = json.loads(docker("inspect", name))[0]
            limits = inspect["HostConfig"]
            assert inspect["Config"]["User"] == "10001:10001"
            assert limits["ReadonlyRootfs"] and "ALL" in limits["CapDrop"]
            assert limits["Memory"] == 512 * 1024**2
            assert limits["MemorySwap"] == limits["Memory"]
            assert limits["NanoCpus"] == 1_000_000_000
            assert limits["PidsLimit"] == 64
            assert request("/api/settings")[0] == 401
            admin = docker("exec", name, "cat", "/config/admin.token")
            monitor = docker("exec", name, "cat", "/config/monitor.token")
            assert request("/api/settings", monitor)[0] == 401
            assert request("/backup-status", monitor)[0] == 503
            status, settings = request("/api/settings", admin)
            assert status == 200
            settings["retention"]["days"] = 91
            assert request("/api/settings", admin, settings)[0] == 200
            docker("exec", name, "sh", "-c", "printf persistent > /exports/sentinel")
            # Recreating exercises volume survival when an image/application is upgraded.
            docker(*compose, "up", "-d", "--force-recreate", "--pull", "never")
            base = "http://" + docker(*compose, "port", "backup", "8765")
            wait_ready()
            assert request("/api/settings", admin)[1]["retention"]["days"] == 91
            assert docker("exec", name, "cat", "/config/monitor.token") == monitor
            assert docker("exec", name, "cat", "/exports/sentinel") == "persistent"
            status_text = docker("exec", name, "cat", "/proc/1/status")
            rss_kib = int(
                next(line for line in status_text.splitlines() if line.startswith("VmRSS:")).split()[1]
            )
            idle_stats = json.loads(docker("stats", "--no-stream", "--format", "{{json .}}", name))
            fixture = json.loads(docker("exec", name, "python", "/smoke/resource_fixture.py"))
            assert request("/health")[0] == 200
            # Cgroup v2 is available on the CI runner. Includes page cache, unlike process RSS.
            events = docker("exec", name, "cat", "/sys/fs/cgroup/memory.events")
            assert "oom_kill 0" in events
            report = {
                "image": image,
                "image_uncompressed_bytes": int(docker("image", "inspect", "--format", "{{.Size}}", image)),
                "memory_limit_mib": 512,
                "cpu_limit": 1,
                "swap_allowed": False,
                "idle_service_rss_mib": round(rss_kib / 1024, 2),
                "idle_docker_memory": idle_stats["MemUsage"],
                "container_peak_bytes_including_file_cache": int(
                    docker("exec", name, "cat", "/sys/fs/cgroup/memory.peak")
                ),
                "cgroup_memory_events": events,
                "synthetic_workload": fixture,
                "checks": "Shipped Compose, non-root, read-only, auth, freshness, recreation with persistent volumes",
            }
            output = root / "build" / "resource-report.json"
            output.parent.mkdir(exist_ok=True)
            output.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
        except Exception:
            subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Status}} exit={{.State.ExitCode}}", name],
                check=False,
            )
            subprocess.run(["docker", "logs", "--tail", "100", name], check=False)
            raise
        finally:
            subprocess.run(["docker", *compose, "down", "--volumes"], capture_output=True, check=False)


if __name__ == "__main__":
    main()
