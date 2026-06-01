# Standalone image for the demographic widget service.
# Mirrors the monolith's slim-python + pip pattern, but is fully self-contained
# (it copies its own src and shares no code with the monolith — see ADR-0001).
FROM python:3.12-slim AS base

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ./src /app/src

# Own dev port (the monolith uses 28000).
EXPOSE 28001

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "28001"]
