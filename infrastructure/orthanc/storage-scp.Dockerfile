FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY infrastructure/orthanc/storage-scp-requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir --requirement /tmp/requirements.txt

COPY scripts/dicom/storage_scp.py /app/scripts/dicom/storage_scp.py
COPY scripts/dicom/storage_scp_health.py /app/scripts/dicom/storage_scp_health.py

CMD ["python", "-m", "scripts.dicom.storage_scp"]
