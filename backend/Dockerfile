FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
COPY pyproject.toml .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Set Python path to include the project root
ENV PYTHONPATH=/app

# Expose the backend port
EXPOSE 8000

# Run the server using uvicorn in production mode
CMD ["uvicorn", "backend.websocket_server:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "error"]