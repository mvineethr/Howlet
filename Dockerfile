FROM python:3.12-slim

WORKDIR /app

# System deps for lxml (libxml2/libxslt) - lxml wheels usually cover this,
# but keep build tools available in case a source build is needed on a
# platform without a matching wheel.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

# Run as a non-root user: the dashboard only needs its own cache dir.
RUN groupadd -r howlet && useradd -r -g howlet -d /home/howlet -m howlet
ENV HOME=/home/howlet
USER howlet

# Dashboard port. The dashboard binds loopback (127.0.0.1) by default, so
# `-p 8813:8813` publishing does NOT reach it: Docker NATs to the
# container's eth0, not its loopback. Reach it with --network host (Linux)
# or run `howlet dashboard` on the host instead. To expose it on the LAN,
# pass --host 0.0.0.0 AND set a dashboard token first:
#   docker run --rm --network host -e EDGAR_USER_AGENT="..." \
#     -e HOWLET_DASHBOARD_TOKEN="..." howlet:latest dashboard
#   docker run --rm -e EDGAR_USER_AGENT="..." -e HOWLET_DASHBOARD_TOKEN="..." \
#     -p 8813:8813 howlet:latest dashboard --host 0.0.0.0
EXPOSE 8813

ENTRYPOINT ["howlet"]
CMD ["--help"]
