"""Run against an isolated Docker engine in CI; no real credentials or mail."""

import json
import subprocess
import time
import urllib.error
import urllib.request
from uuid import uuid4


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def main():
    name = "mnb-test-" + uuid4().hex[:10]
    config, data = name + "-config", name + "-data"
    try:
        docker(
            "run",
            "-d",
            "--name",
            name,
            "--user",
            "10001:10001",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m,mode=1777",
            "-p",
            "127.0.0.1::8765",
            "-v",
            config + ":/config",
            "-v",
            data + ":/data",
            "m365-nas-backup:0.1.0-alpha.1",
        )
        port = docker("port", name, "8765/tcp").rsplit(":", 1)[1]
        base = "http://127.0.0.1:" + port

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
        assert request("/api/settings")[0] == 401
        admin = docker("exec", name, "cat", "/config/admin.token")
        monitor = docker("exec", name, "cat", "/config/monitor.token")
        assert request("/api/settings", monitor)[0] == 401
        assert request("/backup-status", monitor)[0] == 503
        status, settings = request("/api/settings", admin)
        assert status == 200
        settings["retention"]["days"] = 91
        assert request("/api/settings", admin, settings)[0] == 200
        docker("restart", name)
        # Docker may allocate a different ephemeral host port after a restart.
        port = docker("port", name, "8765/tcp").rsplit(":", 1)[1]
        base = "http://127.0.0.1:" + port
        wait_ready()
        assert request("/api/settings", admin)[1]["retention"]["days"] == 91
        assert docker("exec", name, "cat", "/config/monitor.token") == monitor
        print("Container passed: non-root, read-only, authentication, freshness, persisted configuration.")
    except Exception:
        print(docker("inspect", "--format", "{{.State.Status}} exit={{.State.ExitCode}}", name))
        print(docker("logs", "--tail", "100", name))
        raise
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)
        subprocess.run(["docker", "volume", "rm", config, data], capture_output=True, check=False)


if __name__ == "__main__":
    main()
