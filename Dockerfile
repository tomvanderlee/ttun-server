FROM ghcr.io/astral-sh/uv:python3.14-alpine AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_DEV=1
ENV UV_TOOL_BIN_DIR=/usr/local/bin
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked


FROM python:3.14-alpine

RUN addgroup -S -g 10001 nonroot \
  && adduser -S -G nonroot -u 10001 -h /home/nonroot nonroot

COPY --from=builder --chown=nonroot:nonroot /app /app
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app
ARG DOCKER_METADATA_OUTPUT_VERSION
RUN echo "version='$DOCKER_METADATA_OUTPUT_VERSION'" > ttun_server/_version.py

ENV TUNNEL_DOMAIN=''
ENV SECURE=True
EXPOSE 8000

USER nonroot

CMD ["uvicorn", "ttun_server:server", "--host", "0.0.0.0", "--port", "8000"]
