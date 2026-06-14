.PHONY: test dev build run ui

test:
	python -m pytest

dev:
	docker compose -f docker-compose.dev.yml up --build

build:
	docker build -t praim/reuse-service .

run:
	uvicorn src.app:app --host 0.0.0.0 --port 28002 --reload

# Build the UI bundle (the <reuse-widget> custom element) and place it where
# FastAPI serves it. Run once before `make run` to serve /reuse/widget.js
# locally; the Docker image builds it in its own Node stage.
ui:
	cd ui && npm install && npm run build
	mkdir -p src/static
	cp ui/dist/reuse-widget.js src/static/reuse-widget.js
