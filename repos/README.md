# Standalone repos (eve-emu monorepo)

These folders are designed to be copied or pushed to **their own GitHub repositories**. They live under `repos/` for development alongside eve-emu.

| Repo | Purpose |
|------|---------|
| [aa-esi-forwarder](./aa-esi-forwarder/) | AA5: ESI proxy for trusted apps (live EVE data) |
| [aa-report-bridge](./aa-report-bridge/) | AA5: signed webhooks + read-only export API (AA DB snapshots) |
| [great-damn-emu-report](./great-damn-emu-report/) | FastAPI: ingest webhooks, history DB, ESI reports, export sync |

## Split into separate Git remotes

```bash
cd repos/aa-esi-forwarder
git init && git add . && git commit -m "Initial aa-esi-forwarder"

cd ../great-damn-emu-report
git init && git add . && git commit -m "Initial Great Damn EMU Report"
```

## Wire into eve-emu Alliance Auth

In `deploy/aa_docker/local.py`:

```python
INSTALLED_APPS += [
    "aa_esi_forwarder.apps.AaEsiForwarderConfig",
    "aa_report_bridge.apps.AaReportBridgeConfig",
]
```

Copy `aa_esi_forwarder` and `aa_report_bridge` into the AA image (or `pip install` each package).

See [docs/REPORT_BRIDGE.md](../docs/REPORT_BRIDGE.md) for webhooks + export + ESI together.
