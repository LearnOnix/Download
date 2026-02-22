# Use official Python 3.11 slim image (smaller size)
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application
COPY bot.py .
COPY .env .

# Create a non-root user to run the app (security)
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Command to run your bot
CMD ["python", "bot.py"]
