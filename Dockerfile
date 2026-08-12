FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY sales_ivr ./sales_ivr
COPY config.yaml ./config.yaml

RUN pip install --no-cache-dir .

ENV SALES_IVR_CONFIG_PATH=/app/config.yaml
EXPOSE 8000

CMD ["uvicorn", "sales_ivr.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
