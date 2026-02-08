# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.6.4 /uv /bin/uv

# Set the working directory to /app
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy the lockfile and pyproject.toml to install dependencies first (caching layer)
COPY uv.lock pyproject.toml ./

# Install dependencies using uv
# --frozen: use uv.lock exactly
# --no-install-project: don't install the 'itsm-agent' package itself yet
RUN uv sync --frozen --no-install-project --no-dev

# Copy the rest of the application code
COPY . .

# Install the project itself
RUN uv sync --frozen --no-dev

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user for security
RUN useradd -m appuser
USER appuser

# Run the application with proxy headers for ALB/Nginx
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
