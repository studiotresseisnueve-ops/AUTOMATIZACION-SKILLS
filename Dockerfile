# ============================================================
# Autonomous Agent System — Docker Image
# ============================================================
FROM python:3.11-slim

# System dependencies needed by PyMuPDF on Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash agent
WORKDIR /app

# Install Python dependencies first (layer-cached unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code (volumes will override data/, outputs/, src/prompts/ at runtime)
COPY main.py .
COPY src/ ./src/

# Create expected directories so the app never fails on a missing path
RUN mkdir -p data/empresas outputs \
    && chown -R agent:agent /app

USER agent

CMD ["python", "-u", "main.py"]
