#docker build -f src/trendline/Dockerfile -t trendline-algo:local .

FROM python:3.11-bookworm

WORKDIR /app

COPY requirements.txt .
COPY src ./src
COPY resources ./resources
COPY pyproject.toml .

RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app/src:/app/src/trendline

CMD ["python", "src/trendline/trendline.py"]