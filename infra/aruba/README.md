# Deploy `opendata-ai` on an Aruba VPS

Production deployment target after the Azure Container Apps stack was
removed. All four backend services + Postgres + Redis + Caddy live on a
single VPS; the frontend is shipped to GitHub Pages from
`opendata-ai-ui/`.

## What ends up on the host

```
                ┌── opendata.example.com (GitHub Pages)
Browser ◀──────┤
                └── api.opendata.example.com (Aruba VPS)
                             │  Caddy 2 (TLS via Let's Encrypt)
                             ▼
                    ┌──────────────────────┐
                    │   opendata-backend   │ — uvicorn :8000
                    └──────────────────────┘
                       │      │      │      │
                  ckan-mcp ist-mcp osm-mcp  │
                                            ▼
                                  postgres + redis
```

## Prerequisites

- Aruba VPS with Ubuntu 22.04+ and a public IPv4
- DNS records: `api.opendata.<your-domain>` → VPS IP (frontend at
  `opendata.<your-domain>` is the GitHub Pages CNAME → `<gh-user>.github.io`)
- Docker Engine 24+ and the Compose plugin
- A Clerk application (`app_3EMALiLi0UTULl89JPMKtaLENoy`) with at least one
  Webhook endpoint pointing to `https://api.opendata.<domain>/webhooks/clerk`
- Anthropic API key with budget for Sonnet 4.6 (synth) + Haiku 4.5 (classify)

## First-time setup

```bash
# 1. SSH into the VPS and clone the repo.
ssh root@vps.example.com
git clone https://github.com/agent-engineering-studio/opendata-ai.git
cd opendata-ai/infra/aruba

# 2. Fill in the env file.
cp .env.prod.example .env.prod
$EDITOR .env.prod   # set every CHANGE_ME and CLERK_* / ANTHROPIC_API_KEY

# 3. Set the FQDN in the Caddyfile.
$EDITOR Caddyfile   # replace api.opendata.example.com + admin email

# 4. Initialise the agent-stack submodule (read-only) for the canonical
#    opendata.* migrations. Without it, the stub migration in
#    opendata-backend/migrations/versions/ is used.
cd ../../
git submodule update --init --depth=1
cd infra/aruba

# 5. Pull images and bring everything up.
docker compose --env-file .env.prod -f docker-compose.prod.yml pull
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d

# 6. Apply database migrations.
docker compose --env-file .env.prod -f docker-compose.prod.yml \
  exec opendata-backend alembic upgrade head

# 7. Check health.
curl -fsS https://api.opendata.<your-domain>/health
```

## Upgrade

```bash
cd ~/opendata-ai
git pull
cd infra/aruba
docker compose --env-file .env.prod -f docker-compose.prod.yml pull
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
docker compose --env-file .env.prod -f docker-compose.prod.yml \
  exec opendata-backend alembic upgrade head
```

## Rolling back

`docker compose pull` always re-resolves `:latest`. Pin to a specific
short-SHA tag (e.g. `:sha-abc1234`) in `docker-compose.prod.yml` and
`docker compose up -d --force-recreate` to roll back.

## Manual checklist before going live

- [ ] DNS A record for `api.opendata.<your-domain>` points at the VPS
- [ ] DNS CNAME `opendata.<your-domain>` → `<gh-user>.github.io`
- [ ] GitHub Pages source = "GitHub Actions" + custom domain configured
- [ ] Clerk webhook endpoint URL + signing secret saved in `.env.prod`
- [ ] Anthropic budget alerts configured in console.anthropic.com
- [ ] `ufw allow 80,443/tcp && ufw enable` on the VPS
- [ ] Off-host backup of Postgres named volume (e.g. nightly
      `pg_dump | rclone` to S3-compatible storage)
