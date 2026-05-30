# Build from monorepo: docker build -f repos/great-damn-emu-report/Dockerfile -t emu-report repos
FROM python:3.12-slim

WORKDIR /app

COPY great-damn-emu-report/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY great-damn-emu-report/report_app ./report_app
COPY aa-esi-forwarder/esi_forwarder_client ./esi_forwarder_client
COPY aa-report-bridge/report_bridge_client ./report_bridge_client

ENV PYTHONPATH=/app
EXPOSE 8020
CMD ["uvicorn", "report_app.main:app", "--host", "0.0.0.0", "--port", "8020"]
