"""Message template registry and Jinja2 render."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_api_key
from app.db.session import get_db
from app.models import MessageTemplate
from app.schemas import (
    TemplateCreate,
    TemplateOut,
    TemplateRenderIn,
    TemplateRenderOut,
    TemplateUpdate,
)
from app.services.template_engine import parse_variables, render_template

router = APIRouter(prefix="/templates", tags=["Templates"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=list[TemplateOut])
async def list_templates(db: AsyncSession = Depends(get_db)) -> list[MessageTemplate]:
    rows = await db.scalars(select(MessageTemplate).order_by(MessageTemplate.slug))
    return list(rows.all())


@router.post("", response_model=TemplateOut, status_code=201)
async def create_template(
    payload: TemplateCreate, db: AsyncSession = Depends(get_db)
) -> MessageTemplate:
    existing = await db.scalar(select(MessageTemplate).where(MessageTemplate.slug == payload.slug))
    if existing:
        raise HTTPException(status_code=409, detail="Slug already exists")
    row = MessageTemplate(**payload.model_dump())
    db.add(row)
    await db.flush()
    await db.commit()
    return row


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(template_id: int, db: AsyncSession = Depends(get_db)) -> MessageTemplate:
    row = await db.get(MessageTemplate, template_id)
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return row


@router.patch("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: int, payload: TemplateUpdate, db: AsyncSession = Depends(get_db)
) -> MessageTemplate:
    row = await db.get(MessageTemplate, template_id)
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.flush()
    await db.commit()
    return row


@router.post("/{template_id}/render", response_model=TemplateRenderOut)
async def render_message_template(
    template_id: int,
    payload: TemplateRenderIn,
    db: AsyncSession = Depends(get_db),
) -> TemplateRenderOut:
    row = await db.get(MessageTemplate, template_id)
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    subject, body = render_template(row, payload.variables)
    return TemplateRenderOut(subject=subject, body=body)


@router.get("/{template_id}/variables")
async def template_variables(template_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.get(MessageTemplate, template_id)
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"variables": parse_variables(row)}
