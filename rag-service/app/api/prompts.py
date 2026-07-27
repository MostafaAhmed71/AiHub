"""Prompt Library endpoints."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.db.session import get_db
from app.models.schemas import (
    PromptCreate,
    PromptOut,
    PromptRenderRequest,
    PromptRenderResponse,
    PromptUpdate,
)
from app.services.prompts import PromptService

router = APIRouter(prefix="/prompts", tags=["prompts"], dependencies=[Depends(verify_api_key)])
service = PromptService()


@router.post("", response_model=PromptOut, status_code=status.HTTP_201_CREATED)
async def create_prompt(body: PromptCreate, db: AsyncSession = Depends(get_db)):
    prompt = await service.create(
        db,
        category=body.category,
        title=body.title,
        content=body.content,
        variables=body.variables,
        project_id=body.project_id,
    )
    return PromptOut.model_validate(prompt)


@router.get("", response_model=list[PromptOut])
async def list_prompts(
    category: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    include_global: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    prompts = await service.list(
        db,
        category=category,
        project_id=project_id,
        include_global=include_global,
    )
    return [PromptOut.model_validate(p) for p in prompts]


@router.get("/{prompt_id}", response_model=PromptOut)
async def get_prompt(prompt_id: UUID, db: AsyncSession = Depends(get_db)):
    prompt = await service.get(db, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return PromptOut.model_validate(prompt)


@router.patch("/{prompt_id}", response_model=PromptOut)
async def update_prompt(prompt_id: UUID, body: PromptUpdate, db: AsyncSession = Depends(get_db)):
    prompt = await service.get(db, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    updated = await service.update(db, prompt, **body.model_dump(exclude_unset=True))
    return PromptOut.model_validate(updated)


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(prompt_id: UUID, db: AsyncSession = Depends(get_db)):
    prompt = await service.get(db, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    await service.delete(db, prompt)
    return None


@router.post("/{prompt_id}/render", response_model=PromptRenderResponse)
async def render_prompt(
    prompt_id: UUID,
    body: PromptRenderRequest,
    db: AsyncSession = Depends(get_db),
):
    prompt = await service.get(db, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    try:
        rendered = service.render(prompt.content, body.variables)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PromptRenderResponse(prompt_id=prompt.id, rendered=rendered)
