FROM python:3.13-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
RUN pip install --no-cache-dir --no-deps . \
    && groupadd --gid 10001 backup \
    && useradd --uid 10001 --gid backup --no-create-home backup \
    && mkdir /config /data \
    && chown 10001:10001 /config /data
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3)"]
ENTRYPOINT ["m365-backup"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8765"]
