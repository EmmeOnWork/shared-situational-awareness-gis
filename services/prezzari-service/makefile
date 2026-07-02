.PHONY: test dev build run ui

test:
	python -m pytest

build:
	docker build -t praim/prezzari-service .

run:
	uvicorn src.app:app --host 0.0.0.0 --port 28008 --reload

# Build the UI bundle (the <prezzari-widget> custom element) and place it where
# FastAPI serves it. Run once before `make run` to serve /prezzari/widget.js
# locally; the Docker image builds it in its own Node stage.
ui:
	cd ui && npm install && npm run build
	mkdir -p src/static
	cp ui/dist/prezzari-widget.js src/static/prezzari-widget.js
