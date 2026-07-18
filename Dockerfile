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

# Dashboard port; run with:
#   docker run --rm -e EDGAR_USER_AGENT="..." -p 8813:8813 edgar:latest \
#     dashboard --host 0.0.0.0
EXPOSE 8813

ENTRYPOINT ["edgar"]
CMD ["--help"]
