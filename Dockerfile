FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for healthchecks if needed, but minimal)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*


# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers and dependencies
RUN playwright install --with-deps

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application (overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
