# Use the official Microsoft Playwright image which has Python and Browsers pre-installed
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

# Set the working directory
WORKDIR /app

# Copy your requirements file
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Expose the port Streamlit uses
EXPOSE 8501

# Start Streamlit
# Note: Render provides a $PORT environment variable, so we use that
CMD ["streamlit", "run", "app.py", "--server.port", "10000", "--server.address", "0.0.0.0", "--server.enableCORS", "false", "--server.enableXsrfProtection", "false"]
