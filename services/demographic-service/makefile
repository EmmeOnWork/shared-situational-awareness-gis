.PHONY: test dev build run

test:
	python -m pytest

dev:
	docker compose -f docker-compose.dev.yml up --build

build:
	docker build -t praim/demographic-service .

run:
	uvicorn src.app:app --host 0.0.0.0 --port 28001 --reload
