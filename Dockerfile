FROM python:3.9-slim

WORKDIR /chatbot

# Install common dependencies for chatbots
RUN pip install --no-cache-dir \
    dotenv \
    aiogram \
    python-telegram-bot \
    flask \
    requests \
    nltk \
    scikit-learn \
    numpy \
    pandas

# Copy the application
COPY data/ ./data/
COPY .gitignore ./
COPY app/ ./app/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/chatbot

# Expose port (adjust if your chatbot uses a different port)
EXPOSE 8000

# Command to run the chatbot
CMD ["python", "app/main.py"]