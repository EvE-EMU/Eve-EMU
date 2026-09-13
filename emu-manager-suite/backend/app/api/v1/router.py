"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import admin, auth, audit, dashboard, health, identity, knowledge, map, moons, notifications, people, rentals, settings, srp, templates, tools, ui, webhook_notifications

api_v1 = APIRouter()
api_v1.include_router(health.router)
api_v1.include_router(auth.router)
api_v1.include_router(admin.router)
api_v1.include_router(map.router)
api_v1.include_router(identity.router)
api_v1.include_router(people.router)
api_v1.include_router(audit.router)
api_v1.include_router(dashboard.router)
api_v1.include_router(settings.router)
api_v1.include_router(moons.router)
api_v1.include_router(rentals.router)
api_v1.include_router(templates.router)
api_v1.include_router(ui.router)
api_v1.include_router(notifications.router)
api_v1.include_router(webhook_notifications.router)
api_v1.include_router(srp.router)
api_v1.include_router(knowledge.router)
api_v1.include_router(tools.router)
