FROM python:3.13-slim-bookworm
LABEL org.opencontainers.image.source="https://github.com/dicorengineering/m365-nas-backup" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.title="M365 NAS Backup" \
      org.opencontainers.image.description="AI-written experimental Exchange backup; see bundled license and disclaimer."
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# Keep timezone data aligned with the current signed Debian source index.
RUN apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends --only-upgrade tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt pyproject.toml README.md LICENSE DISCLAIMER.md THIRD_PARTY_NOTICES.md ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY scripts/collect_licenses.py /tmp/collect_licenses.py
RUN pip install --no-cache-dir --no-deps . \
    && python /tmp/collect_licenses.py --output /usr/share/m365-nas-backup/licenses \
    && cp LICENSE DISCLAIMER.md THIRD_PARTY_NOTICES.md /usr/share/m365-nas-backup/licenses/ \
    && rm /tmp/collect_licenses.py \
    && groupadd --gid 10001 m365backup \
    && useradd --uid 10001 --gid m365backup --no-create-home --shell /usr/sbin/nologin m365backup \
    && mkdir /config /data /exports \
    && chown 10001:10001 /config /data /exports \
    && chmod 700 /config /data /exports
COPY third_party/licenses/MPL-2.0.txt /usr/share/m365-nas-backup/licenses/MPL-2.0.txt
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=60s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3)"]
ENTRYPOINT ["m365-backup"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8765"]
