FROM python:3.10-slim

WORKDIR /app

# Копируем зависимости и устанавливаем
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Запускаем uvicorn (порт берётся из $PORT по умолчанию на Render)
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
