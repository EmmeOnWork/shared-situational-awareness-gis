# Standalone image for the geo-layers service — a pure data-source Widget that
# serves GeoJSON map layers to the monolith's GIS map (no UI bundle, so no Node
# stage). Copies its own src and shares no code with the monolith (ADR-0001).

FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ./src /app/src

RUN groupadd -r app && useradd -r -g app app && chown -R app:app /app

# Own dev port (reachable only through the gateway, ADR-0002).
EXPOSE 28006
USER app

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "28006"]
