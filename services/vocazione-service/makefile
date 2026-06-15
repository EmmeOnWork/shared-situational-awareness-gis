.PHONY: test build run ui

test:
	python -m pytest

build:
	docker build -t praim/vocazione-service .

run:
	uvicorn src.app:app --host 0.0.0.0 --port 28003 --reload

# Build the UI bundle (the <vocazione-widget> custom element) and place it where
# FastAPI serves it. Run once before `make run` to serve /vocazione/widget.js
# locally; the Docker image builds it in its own Node stage.
ui:
	cd ui && npm install && npm run build
	mkdir -p src/static
	cp ui/dist/vocazione-widget.js src/static/vocazione-widget.js
