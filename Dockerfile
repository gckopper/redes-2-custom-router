FROM python:3.12-trixie
RUN apt-get update
COPY --from=ghcr.io/astral-sh/uv:0.8.19 /uv /uvx /bin/

RUN apt-get install -y iproute2 tcpdump iputils-ping

# Copy the project into the image
ADD . /app

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /app

RUN uv sync --locked


CMD ["uv", "run", "main.py"]
