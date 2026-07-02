FROM python:3.11-slim

WORKDIR /app

# Copy all project files into the container
COPY . /app

# Expose port (Render will route traffic automatically)
EXPOSE 3000

# Start command
CMD ["python", "server.py"]
