# syntax=docker/dockerfile:1.4
# ─── Backend Dockerfile (Optimized) ─────────────────────
# Multi-stage: deps → production
#
# Layer order: dependency specs → install third-party wheels → copy app → install local package only.
# Code changes under app/ do not invalidate the heavy "pip install dependencies" layer.
#
# BuildKit: DOCKER_BUILDKIT=1 so pip cache mount persists wheel downloads between builds.
FROM python:3.12-slim AS deps

# Set to 0 to keep official deb.debian.org / security.debian.org (e.g. CI outside CN).
ARG CLAWITH_APT_MIRROR=1

WORKDIR /app
RUN set -eux; \
    if [ "${CLAWITH_APT_MIRROR}" = "1" ]; then \
      find /etc/apt -type f \( -name '*.list' -o -name '*.sources' \) -print0 \
        | xargs -0r sed -i \
            's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g'; \
    fi; \
    apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Only dependency declarations — changing app/ does not bust this layer.
COPY pyproject.toml ./

ARG CLAWITH_PIP_INDEX_URL
ARG CLAWITH_PIP_TRUSTED_HOST
ARG CLAWITH_PIP_EXTRA_INDEX_URL

# 1) Install all third-party packages from [project].dependencies (no app/ tree needed).
# 2) Copy source and install the clawith-backend package without re-resolving deps.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    python -c "import pathlib, tomllib; \
    data = tomllib.loads(pathlib.Path('pyproject.toml').read_bytes()); \
    pathlib.Path('.docker-project-deps.txt').write_text( \
        '\n'.join(data['project']['dependencies']) + '\n')" && \
    EXTRA=""; \
    if [ -n "$CLAWITH_PIP_EXTRA_INDEX_URL" ]; then EXTRA="$EXTRA --extra-index-url=$CLAWITH_PIP_EXTRA_INDEX_URL"; fi && \
    if [ -n "$CLAWITH_PIP_INDEX_URL" ] && [ -n "$CLAWITH_PIP_TRUSTED_HOST" ]; then \
        pip install --index-url "$CLAWITH_PIP_INDEX_URL" --trusted-host "$CLAWITH_PIP_TRUSTED_HOST" $EXTRA -r .docker-project-deps.txt; \
    elif [ -n "$CLAWITH_PIP_INDEX_URL" ]; then \
        pip install --index-url "$CLAWITH_PIP_INDEX_URL" $EXTRA -r .docker-project-deps.txt; \
    else \
        pip install $EXTRA -r .docker-project-deps.txt; \
    fi

COPY app ./app

RUN --mount=type=cache,target=/root/.cache/pip \
    EXTRA=""; \
    if [ -n "$CLAWITH_PIP_EXTRA_INDEX_URL" ]; then EXTRA="$EXTRA --extra-index-url=$CLAWITH_PIP_EXTRA_INDEX_URL"; fi && \
    if [ -n "$CLAWITH_PIP_INDEX_URL" ] && [ -n "$CLAWITH_PIP_TRUSTED_HOST" ]; then \
        pip install --index-url "$CLAWITH_PIP_INDEX_URL" --trusted-host "$CLAWITH_PIP_TRUSTED_HOST" $EXTRA --no-deps .; \
    elif [ -n "$CLAWITH_PIP_INDEX_URL" ]; then \
        pip install --index-url "$CLAWITH_PIP_INDEX_URL" $EXTRA --no-deps .; \
    else \
        pip install $EXTRA --no-deps .; \
    fi

# ─── Production ─────────────────────────────────────────
FROM python:3.12-slim AS production

ARG CLAWITH_APT_MIRROR=1

WORKDIR /app
RUN set -eux; \
    if [ "${CLAWITH_APT_MIRROR}" = "1" ]; then \
      find /etc/apt -type f \( -name '*.list' -o -name '*.sources' \) -print0 \
        | xargs -0r sed -i \
            's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g'; \
    fi; \
    apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl shadowsocks-libev gosu && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=deps /usr/local/bin/ /usr/local/bin/

# Copy application code
COPY . .

RUN useradd --create-home clawith && \
    mkdir -p /data/agents && \
    chmod +x /app/entrypoint.sh && \
    chown -R clawith:clawith /app /data

# Note: USER is removed to allow entrypoint.sh to fix permissions of mounted volumes
# at runtime. The entrypoint script will drop privileges to 'clawith' after fixing permissions.

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000
# entrypoint.sh runs `alembic upgrade head` then `uvicorn`
ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
