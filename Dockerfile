FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Устанавливаем системные зависимости, необходимые для Qt
RUN apt-get update && apt-get install -y --no-install-recommends \
    libx11-xcb1 \
    libxcb1 \
    libx11-6 \
    libxcb-render0 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxkbcommon-x11-0 \
    libglu1-mesa \
    libxrender1 \
    libxext6 \
    libsm6 \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir PyQt5

# Копируем исходники в образ
COPY main.py /app/main.py
COPY sketches /app/sketches

# По умолчанию база будет монтироваться как volume, поэтому не копируем файл БД принудительно

CMD ["python", "main.py"]



