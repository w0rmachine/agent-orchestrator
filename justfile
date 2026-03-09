set shell := ["bash", "-cu"]

backend:
	uv run -m uvicorn backend.main:app --reload --port 8000

frontend:
	cd frontend && npm install
	cd frontend && npm run dev

dev:
	just backend &
	just frontend &
	wait
