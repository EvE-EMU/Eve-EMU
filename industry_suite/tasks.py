"""
Celery tasks for heavy ESI pulls (moon ledgers, corp industry, audits).

Wire these in your Alliance Auth deployment's Celery app; import paths stay stable
once ``industry_suite`` is on ``INSTALLED_APPS`` and ``django-eveuniverse`` / your
ESI client is configured.

Example (sketch only)::

    from celery import shared_task

    @shared_task
    def refresh_suborder_statuses(project_id: int) -> None:
        ...
"""

# Intentionally empty: operators bind tasks to their Celery configuration.
