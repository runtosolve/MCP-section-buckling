FROM julia:1.12-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV JULIA_PKG_USE_CLI_GIT=true

COPY Project.toml Manifest.toml ./
RUN julia --project=. -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'

COPY requirements.txt .
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

COPY backend.jl server.py config.py ./
COPY backend ./backend
COPY tools ./tools

EXPOSE 8000 8081
