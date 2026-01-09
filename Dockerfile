# Base Image
FROM python:3.11-slim

# Working Directory
WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Source Code
COPY . .

# Environment Defaults
ENV CHECK_INTERVAL=60

# Command
# By default, run the Bot Brain.
# To run Portal: docker run -p 8501:8501 image streamlit run portal.py
CMD ["python", "bot_brain.py"]
