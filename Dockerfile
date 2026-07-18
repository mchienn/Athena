FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    HOME=/tmp

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY hanoi_heart_assistant ./hanoi_heart_assistant
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 athena \
    && chown -R athena:athena /tmp
USER athena

CMD ["python", "-m", "hanoi_heart_assistant.runtime"]
