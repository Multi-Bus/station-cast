FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md constraints.txt ./
COPY src/ ./src/

RUN pip install --no-cache-dir -c constraints.txt .

EXPOSE 8000

CMD ["uvicorn", "stationcast.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
