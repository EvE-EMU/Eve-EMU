# Alliance Auth (v5) in EVE-EMU

This repository vendors **[Alliance Auth](https://allianceauth.readthedocs.io/en/v5.0.1/)** as a **[Git submodule](https://git-scm.com/book/en/v2/Git-Tools-Submodules)** at **`allianceauth/`**, pinned to upstream tag **`v5.0.1`** (Django-based auth hub for EVE organizations: services, groups, fleet tools, SRP apps, etc.—see the [official overview](https://allianceauth.readthedocs.io/en/v5.0.1/)).

Canonical upstream source: **https://gitlab.com/allianceauth/allianceauth** (the GitHub mirror is stale).

## License

Alliance Auth is **GPLv2**. If you ship a combined product that includes AA, comply with the GPL (this submodule preserves upstream history and the `LICENSE` file under `allianceauth/`).

## Fork for your org

1. On GitLab (or GitHub if you mirror), **fork** `allianceauth/allianceauth` to your namespace.
2. In this repo, point the submodule at your fork:

   ```bash
   git config submodule.allianceauth.url https://gitlab.com/<you>/allianceauth.git
   # or edit .gitmodules then:
   git submodule sync
   ```

3. Optionally create a branch on your fork (e.g. `eve-emu-patches`) and set the submodule to track that branch instead of detached tags—then merge upstream `v5.x` releases as needed.

## Running AA locally (recommended: Linux or Docker)

Upstream targets **Linux** (see PyPI classifiers). On Windows, use **WSL2** or **Docker** rather than native installs.

High-level steps (details in [Alliance Auth installation docs](https://allianceauth.readthedocs.io/en/v5.0.1/installation/index.html)):

1. **Python 3.10–3.13**, **PostgreSQL**, **Redis**, **Celery** worker + beat (AA expects them).
2. Create a **Django project** that installs `allianceauth` from the submodule path or from PyPI at the same version as the tag you use.
3. Configure **EVE developer application** (SSO client id/secret) and callback URLs per AA settings.
4. Run migrations, collectstatic, and serve with **gunicorn** + reverse proxy (see [Gunicorn](https://allianceauth.readthedocs.io/en/v5.0.1/installation/gunicorn.html) / [NGINX](https://allianceauth.readthedocs.io/en/v5.0.1/installation/nginx.html) in the docs).

Container-oriented install: [Installation — Containerized / Docker](https://allianceauth.readthedocs.io/en/v5.0.1/installation-containerized/docker.html).

## Relationship to `core/` (FastAPI) and `core-web/` (Next.js)

| Component | Role |
|-----------|------|
| **`allianceauth/`** | Primary **alliance-style** web portal (users, groups, services, community apps)—closest to “main app” for org operations. |
| **`core/`** | **FastAPI** API: SDE, Discord-bot plugin routes, optional shared SSO/token store for bots—keep as a **service** other clients call. |
| **`core-web/`** | Optional **Next.js** shell for custom pages that call `core/` if you do not implement those inside AA apps. |

Integrating AA with `core/` deeply (single sign-on, one user table) is **non-trivial**: AA uses **Django** + **django-esi**; `core/` uses its own models and EVE SSO flow. Practical phases:

1. **Side-by-side:** Deploy AA for humans; keep `core/` for APIs and the Discord bot; accept two EVE apps or two callback URLs until you unify.
2. **Later:** Add a small bridge (e.g. shared Redis events, or HTTP webhooks from AA to `core/`) only where you need cross-system truth.

## Updating the submodule to a newer AA release

```bash
cd allianceauth
git fetch --tags origin
git checkout v5.0.2   # example newer tag
cd ..
git add allianceauth
git commit -m "Bump allianceauth submodule to v5.0.2"
```

## Submodule clone for new developers

After `git clone` of eve-emu:

```bash
git submodule update --init --recursive
```

If you skipped submodules at clone time:

```bash
git submodule update --init allianceauth
```
