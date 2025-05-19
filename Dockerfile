FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y gcc python3-dev sqlite3

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "your_bot_file.py"]
