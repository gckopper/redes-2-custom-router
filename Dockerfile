FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:0.8.19 /uv /uvx /bin/

# Copy the project into the image
ADD . /app

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /app

RUN uv sync --locked

CMD ["uv", "run", "main.py"]
