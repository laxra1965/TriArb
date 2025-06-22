# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies (if any, e.g., for psycopg2 if not using -binary or for other libs)
# RUN apt-get update && apt-get install -y ... && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code into the container
COPY . /app/

# Expose port (gunicorn will run on this port)
EXPOSE 8000

# Command to run the application (using gunicorn as an example WSGI server)
# This assumes manage.py and the project directory arbitrage_platform are in /app/
# For development, one might run manage.py runserver. For production, gunicorn.
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "arbitrage_platform.wsgi:application"]
