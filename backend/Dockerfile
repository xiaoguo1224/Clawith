# syntax=docker/dockerfile:1.4
# ─── Backend Dockerfile (Optimized) ─────────────────────
# Multi-stage: deps → production
#
# BuildKit: use `docker buildx build` or DOCKER_BUILDKIT=1 so the pip cache mount
# below persists wheel downloads between builds (large deps still re-install into
# site-packages when COPY app/ or pyproject.toml changes, but downloads are fast).
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

COPY pyproject.toml ./
# setuptools package discovery needs the `app` tree; without it `pip install .` fails at image build.
COPY app ./app

ARG CLAWITH_PIP_INDEX_URL
ARG CLAWITH_PIP_TRUSTED_HOST
# Optional: e.g. https://pypi.org/simple — use when the primary mirror is missing wheels (pandas/scipy/sklearn, etc.).
ARG CLAWITH_PIP_EXTRA_INDEX_URL

# --mount=type=cache: pip reuses downloaded wheels across builds (not in image layers).
# Omit --no-cache-dir here so pip can write to /root/.cache/pip on that mount.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    EXTRA=""; \
    if [ -n "$CLAWITH_PIP_EXTRA_INDEX_URL" ]; then EXTRA="$EXTRA --extra-index-url=$CLAWITH_PIP_EXTRA_INDEX_URL"; fi && \
    if [ -n "$CLAWITH_PIP_INDEX_URL" ] && [ -n "$CLAWITH_PIP_TRUSTED_HOST" ]; then \
        pip install --index-url "$CLAWITH_PIP_INDEX_URL" --trusted-host "$CLAWITH_PIP_TRUSTED_HOST" $EXTRA .; \
    elif [ -n "$CLAWITH_PIP_INDEX_URL" ]; then \
        pip install --index-url "$CLAWITH_PIP_INDEX_URL" $EXTRA .; \
    else \
        pip install $EXTRA .; \
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
