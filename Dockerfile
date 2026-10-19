FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose Web Dashboard port
EXPOSE 8080

# Run Dashboard
CMD ["python", "app.py"]
