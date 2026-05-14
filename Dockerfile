FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip==25.3 wheel==0.46.2

COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY src/ ./src/
COPY tests/ ./tests/
RUN pip install --no-cache-dir -e .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "restaurant_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
