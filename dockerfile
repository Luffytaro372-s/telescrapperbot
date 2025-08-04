FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY main.py .

# Create directory for session files
RUN mkdir -p /app/data

# Run the bot
CMD ["python", "main.py"]
