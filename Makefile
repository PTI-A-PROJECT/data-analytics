.PHONY: up dev-up down test test-db-up test-db-down backup-db

# Deployment pilot (co-located, port tidak diekspos ke host) — butuh
# `docker network create app-network` sekali saja, dibuat oleh stack aplikasi
# utama. Lihat docker-compose.yml.
up:
	docker compose up -d --build

# Dev lokal: port diekspos ke host, hot-reload aktif, tanpa resource limit.
dev-up:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

down:
	docker compose down

test:
	uv run pytest

# Postgres + pgvector untuk test suite (tests/conftest.py, TEST_DATABASE_URL).
test-db-up:
	docker run -d --name analytics-test-db -p 5433:5432 \
		-e POSTGRES_USER=analytics -e POSTGRES_PASSWORD=analytics \
		-e POSTGRES_DB=analytics_test pgvector/pgvector:pg16

test-db-down:
	docker rm -f analytics-test-db

# Dump manual analytics-db ke ./backups/ (buat direktori itu dulu kalau belum
# ada). Jadwalkan lewat cron VPS untuk backup berkala — lihat README bagian
# "Backup database".
backup-db:
	docker compose exec -T analytics-db pg_dump -U $${POSTGRES_USER} $${POSTGRES_DB} \
		> backups/analytics_$$(date +%Y%m%d_%H%M%S).sql
