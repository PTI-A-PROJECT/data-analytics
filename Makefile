.PHONY: up dev-up down migrate test anonymize anonymize-dry-run backup-db

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

migrate:
	docker compose exec analytics-api uv run --no-sync alembic upgrade head

test:
	uv run pytest

# Cron bulanan UU PDP (lihat .scratch/osn-data-analytics/issues/12-...) —
# contoh crontab ada di bawah.
anonymize:
	docker compose exec analytics-api curl -s -X POST \
		-H "X-Internal-Token: $${INTERNAL_API_TOKEN}" \
		http://localhost:8000/api/v1/admin/anonymize-expired

anonymize-dry-run:
	docker compose exec analytics-api curl -s -X POST \
		-H "X-Internal-Token: $${INTERNAL_API_TOKEN}" \
		"http://localhost:8000/api/v1/admin/anonymize-expired?dry_run=true"

# Dump manual analytics-db ke ./backups/ (buat direktori itu dulu kalau belum
# ada). Jadwalkan lewat cron VPS untuk backup berkala — lihat README bagian
# "Backup database".
backup-db:
	docker compose exec -T analytics-db pg_dump -U $${POSTGRES_USER} $${POSTGRES_DB} \
		> backups/analytics_$$(date +%Y%m%d_%H%M%S).sql
