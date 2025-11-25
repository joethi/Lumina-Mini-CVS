# Dockerfile for Streamlit frontend

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY ../requirements.txt .
RUN pip install --no-cache-dir streamlit requests

# Copy application
COPY app.py .

# Expose port
EXPOSE 8501

# Set environment variable
ENV BACKEND_URL=http://localhost:8000

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
