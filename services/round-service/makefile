.PHONY: test dev build run ui

test:
	python -m pytest

build:
	docker build -t praim/round-service .

run:
	uvicorn src.app:app --host 0.0.0.0 --port 28005 --reload

# Build the UI bundle (the <round-widget> custom element) and place it where
# FastAPI serves it. Run once before `make run` to serve /rounds/widget.js
# locally; the Docker image builds it in its own Node stage.
ui:
	cd ui && npm install && npm run build
	mkdir -p src/static
	cp ui/dist/round-widget.js src/static/round-widget.js
