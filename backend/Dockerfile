FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Prefer requirements.txt (exported via Poetry) for faster, simpler builds.
# Falls back to Poetry if requirements.txt is not present in build context.
COPY requirements.txt ./
COPY pyproject.toml poetry.lock ./
RUN if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        pip install --no-cache-dir poetry && \
        poetry config virtualenvs.create false && \
        poetry install --without dev --no-ansi --no-interaction; \
    fi

# Copy application code
COPY . .

# Create media directory
RUN mkdir -p /app/media/uploads /app/media/encrypted

# Expose port
EXPOSE 8000

# Default command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
