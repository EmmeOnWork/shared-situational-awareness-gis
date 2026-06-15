# Standalone image for the vocazione widget service (Vocazione Selector).
# Full-stack Widget: a Node stage builds the UI bundle (the custom element), a
# Python stage runs the FastAPI service that serves BOTH /health and that bundle.
# It copies its own src and shares no code with the monolith (ADR-0001).

# --- UI stage: build the <vocazione-widget> custom element bundle -------------
FROM node:20-slim AS ui-build
WORKDIR /ui
COPY ui/package.json ./
RUN npm install
COPY ui/ ./
RUN npm run build   # → /ui/dist/vocazione-widget.js

# --- App stage: FastAPI service ----------------------------------------------
FROM python:3.12-slim AS base

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ./src /app/src

# Drop the built UI bundle where FastAPI serves it (/vocazione/widget.js).
COPY --from=ui-build /ui/dist/vocazione-widget.js /app/src/static/vocazione-widget.js

# Create a non-root user and give ownership of the app directory to it
RUN groupadd -r app && useradd -r -g app app \
	&& chown -R app:app /app


# Own dev port (monolith 28000, demographic 28001, characteristic/reuse 28002).
EXPOSE 28003
USER app

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "28003"]
