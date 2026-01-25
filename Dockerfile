# syntax=docker/dockerfile:1

# Crossyword Dockerfile
# Multi-stage build using uv for fast, reproducible builds

# --- Build stage ---
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1
# Disable uv cache to reduce image size
ENV UV_NO_CACHE=1
# Use copy link mode for faster builds
ENV UV_LINK_MODE=copy

# Install dependencies first (cached layer)
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

# Copy source and install the project
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev


# --- Runtime stage ---
FROM python:3.13-slim-bookworm AS runtime

WORKDIR /app

# Create non-root user for security
RUN groupadd --gid 1000 crossyword && \
    useradd --uid 1000 --gid crossyword --shell /bin/bash --create-home crossyword

# Copy the virtual environment and source from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Set up paths
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

# Create directories for data persistence
RUN mkdir -p /app/data /app/puzzles /app/certs && \
    chown -R crossyword:crossyword /app

# Default configuration via environment variables
ENV CROSSYWORD_DATABASE_URL="sqlite:////app/data/crossyword.db"
ENV CROSSYWORD_PUZZLES_DIR="/app/puzzles"
ENV CROSSYWORD_HOST="0.0.0.0"
ENV CROSSYWORD_PORT="1965"
ENV CROSSYWORD_CERTFILE="/app/certs/cert.pem"
ENV CROSSYWORD_KEYFILE="/app/certs/key.pem"

# Switch to non-root user
USER crossyword

# Expose Gemini port
EXPOSE 1965

# Health check - verify the process is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f crossyword || exit 1

# Run the application
CMD ["crossyword"]
