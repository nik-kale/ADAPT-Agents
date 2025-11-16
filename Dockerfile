# ADAPT-Agents Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 adapt && chown -R adapt:adapt /app
USER adapt

# Expose ports
EXPOSE 8000 9090

# Default command (can be overridden)
CMD ["python", "-m", "api.server"]
