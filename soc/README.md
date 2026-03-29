# SOC (local Splunk)

Splunk runs in Docker via `docker-compose.yml`.

```bash
cd soc
docker compose up -d
```

- **UI:** https://localhost:8000 — `admin` / `ChangeMe123!`
- **API (scripts):** port `8089` — used by `scripts/setup_splunk.py`.

The **Splunk Add-on for AWS** is not bundled here; install from Splunkbase — see [`add-on/README.md`](add-on/README.md).
