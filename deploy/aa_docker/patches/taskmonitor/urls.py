"""Routes for Task Monitor."""

from django.urls import path

from . import views

app_name = "taskmonitor"

urlpatterns = [
    path(
        "admin_taskmonitor_download_csv",
        views.admin_taskmonitor_download_csv,
        name="admin_taskmonitor_download_csv",
    ),
    path(
        "admin_taskmonitor_reports",
        views.admin_taskmonitor_reports,
        name="admin_taskmonitor_reports",
    ),
    path(
        "admin_taskmonitor_reports_clear_cache",
        views.admin_taskmonitor_reports_clear_cache,
        name="admin_taskmonitor_reports_clear_cache",
    ),
    path(
        "admin_taskmonitor_reports_recalculation",
        views.admin_taskmonitor_reports_recalculation,
        name="admin_taskmonitor_reports_recalculation",
    ),
    path(
        "admin_taskmonitor_report_json/<str:report_name>",
        views.admin_taskmonitor_report_json,
        name="admin_taskmonitor_report_json",
    ),
    path(
        "admin_taskmonitor_report_html/<str:report_name>",
        views.admin_taskmonitor_report_html,
        name="admin_taskmonitor_report_html",
    ),
    path(
        "admin_taskmonitor_report_debug/<str:report_name>",
        views.admin_taskmonitor_report_debug,
        name="admin_taskmonitor_report_debug",
    ),
    path(
        "admin_queued_task_purge",
        views.admin_queued_task_purge,
        name="admin_queued_task_purge",
    ),
    path(
        "admin_queued_task_clear_cache",
        views.admin_queued_task_clear_cache,
        name="admin_queued_task_clear_cache",
    ),
    path(
        "admin_queued_task_kill/<uuid:task_id>",
        views.admin_queued_task_kill,
        name="admin_queued_task_kill",
    ),
    path(
        "admin_taskmonitor_statistics_clear_cache",
        views.admin_taskmonitor_statistics_clear_cache,
        name="admin_taskmonitor_statistics_clear_cache",
    ),
]
