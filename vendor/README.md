# `vendor/` — third-party / sibling-project read-only sources

## `vendor/agent-stack/`

Submodule pointing at the [`agent-stack`](https://github.com/agent-engineering-studio/agent-stack)
mono-repo. The directory is empty until you run:

```bash
git submodule update --init --depth=1
```

We consume the `opendata.*` Postgres schema migrations from
`vendor/agent-stack/db/migrations/opendata/` and apply them via Alembic from
`opendata-backend/`. Migrations are owned by `agent-stack`; do not edit
them here.

While the submodule is uninitialised — for example in CI environments that
cannot fetch the private repo — `opendata-backend/migrations/versions/`
ships a **stub** initial migration that mirrors the shape we expect. Once
the submodule materialises, swap the stub for `vendor/agent-stack/db/...`
in `alembic.ini`.
