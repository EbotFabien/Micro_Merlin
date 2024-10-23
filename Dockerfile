# Use an official Python runtime as a parent image
FROM python:slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Copy the .env file into the container
COPY .env /app/.env

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r req.txt

# Expose port 5002 for the app
EXPOSE 5002

# Define environment variable (optional)
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "realtimeapi:app", "--host", "0.0.0.0", "--port", "5002"]