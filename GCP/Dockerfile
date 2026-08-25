FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rankscale_extract_gcp.py .

ENTRYPOINT ["python", "rankscale_extract_gcp.py"]
