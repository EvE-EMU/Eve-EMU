FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app

COPY wh_intel/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY wh_intel /app

EXPOSE 8020
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8020"]
