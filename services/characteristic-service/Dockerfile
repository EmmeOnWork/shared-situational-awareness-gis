# Standalone image for the characteristic widget service.
# Full-stack Widget: a Node stage builds the UI bundle (the custom element), a
# Python stage runs the FastAPI service that serves BOTH the API and that bundle.
# It copies its own src and shares no code with the monolith (ADR-0001).

# --- UI stage: build the <characteristic-widget> custom element bundle --------
FROM node:20-slim AS ui-build
WORKDIR /ui
COPY ui/package.json ./
RUN npm install
COPY ui/ ./
RUN npm run build   # → /ui/dist/characteristic-widget.js

# --- App stage: FastAPI service ----------------------------------------------
FROM python:3.12-slim AS base

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ./src /app/src

# Drop the built UI bundle where FastAPI serves it (/characteristic/widget.js).
COPY --from=ui-build /ui/dist/characteristic-widget.js /app/src/static/characteristic-widget.js

# Create a non-root user and give ownership of the app directory to it
RUN groupadd -r app && useradd -r -g app app \
	&& chown -R app:app /app


# Own dev port (the monolith uses 28000, the demographic widget 28001).
EXPOSE 28002
USER app

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "28002"]
