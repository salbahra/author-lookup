# Use an official lightweight Python image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy requirements.txt if you have one, otherwise skip and install inline
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Flask app code into the container
COPY app.py . 

# Expose the port your app runs on, e.g., 5000
EXPOSE 5000

# Run the Flask app
CMD ["python", "app.py"]
