FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/outbox
RUN mkdir -p /app/reports

ENV PYTHONUNBUFFERED=1

EXPOSE 10000

CMD ["uvicorn","main:app","--host","0.0.0.0","--port","10000"]