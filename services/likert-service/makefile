.PHONY: test dev build run ui refresh

test:
	python -m pytest

# Run one background refresh pass: resolve new competitor identities, then refresh the
# ratings whose TTL has lapsed (up to MONTHLY_BUDGET) across all comuni. Schedule this
# on cron per TTL period; it resumes next period if the budget stops it mid-pass. The
# data route only ever reads the cache this fills — the widget never calls Google.
refresh:
	python -m src.routers.likert.refresh_worker

build:
	docker build -t praim/likert-service .

run:
	uvicorn src.app:app --host 0.0.0.0 --port 28007 --reload

# Build the UI bundle (the <likert-widget> custom element) and place it where
# FastAPI serves it. Run once before `make run` to serve /likert/widget.js
# locally; the Docker image builds it in its own Node stage.
ui:
	cd ui && npm install && npm run build
	mkdir -p src/static
	cp ui/dist/likert-widget.js src/static/likert-widget.js
