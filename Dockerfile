# Base image: official Python on Debian Bookworm "slim" (smaller footprint than the non-slim image).
# Pin 3.12.x here so automated rebuilds do not jump to a new Python minor without you noticing.
FROM python:3.12-slim-bookworm

# Environment variables seen by every RUN/CMD layer and by your Python process:
# PYTHONDONTWRITEBYTECODE=1 — do not write .pyc files into the image (fewer writes, slightly smaller tree).
# PYTHONUNBUFFERED=1 — stdout/stderr are not fully block-buffered; logs appear quickly in `docker logs` / Kubernetes logs.
# PIP_NO_CACHE_DIR=1 — pip does not retain a wheel cache inside the layer (smaller final image).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Working directory inside the image; created if missing. Later COPY/RUN paths are relative to here unless absolute.
WORKDIR /app

# OS-level compilers/headers for Python packages that build native extensions during pip install.
# --no-install-recommends avoids pulling in weak "recommended" packages; deleting /var/lib/apt/lists/* trims layer size.
# Remove this RUN entirely if your requirements install as pure wheels and never need a compiler.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only the dependency manifest first: Docker caches this layer until requirements.txt changes, so editing
# application code does not always force a full reinstall of all Python packages on rebuild.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the project into /app (honors .dockerignore — keep secrets and bulky dirs out of the build context).
COPY . .

# Create a dedicated non-root account and give it ownership of the app tree (needed if Streamlit or deps write under /app).
# USER 10001 uses a numeric UID so Kubernetes `runAsNonRoot` and cross-image portability do not depend on passwd name lookups.
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER 10001

# Documents the container's listening port for humans and for `docker run -P`; it does not publish the port by itself.
EXPOSE 8501

# CMD uses JSON "exec" form: streamlit is PID 1 without a shell wrapper, so SIGTERM from `docker stop` / kubelet reaches it cleanly.
# Replace trendline_streamlit.py with your entry script (path relative to WORKDIR unless you use an absolute path).
# --server.port — Streamlit HTTP port inside the container (match EXPOSE and your Service targetPort in Kubernetes).
# --server.address=0.0.0.0 — listen on all interfaces so traffic from `docker run -p` or in-cluster networking can reach the app.
# --server.headless=true — server/container mode (avoids assumptions that a local desktop browser session is available).
CMD ["streamlit", "run", "trendline_streamlit.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]