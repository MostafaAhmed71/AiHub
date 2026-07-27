"""Prompt Library CRUD + variable rendering."""

from __future__ import annotations

import re
import uuid
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Prompt


_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class PromptService:
    async def create(
        self,
        db: AsyncSession,
        *,
        category: str,
        title: str,
        content: str,
        variables: list[str],
        project_id: Optional[str],
    ) -> Prompt:
        prompt = Prompt(
            category=category,
            title=title,
            content=content,
            variables=variables,
            project_id=project_id,
        )
        db.add(prompt)
        await db.flush()
        await db.refresh(prompt)
        return prompt

    async def list(
        self,
        db: AsyncSession,
        *,
        category: Optional[str] = None,
        project_id: Optional[str] = None,
        include_global: bool = True,
    ) -> list[Prompt]:
        stmt = select(Prompt).order_by(Prompt.category, Prompt.title)
        if category:
            stmt = stmt.where(Prompt.category == category)
        if project_id:
            if include_global:
                stmt = stmt.where(or_(Prompt.project_id == project_id, Prompt.project_id.is_(None)))
            else:
                stmt = stmt.where(Prompt.project_id == project_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, prompt_id: uuid.UUID) -> Optional[Prompt]:
        result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
        return result.scalar_one_or_none()

    async def update(
        self,
        db: AsyncSession,
        prompt: Prompt,
        **fields,
    ) -> Prompt:
        for key, value in fields.items():
            if value is not None:
                setattr(prompt, key, value)
        await db.flush()
        await db.refresh(prompt)
        return prompt

    async def delete(self, db: AsyncSession, prompt: Prompt) -> None:
        await db.delete(prompt)
        await db.flush()

    @staticmethod
    def render(content: str, variables: dict[str, str]) -> str:
        def replacer(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in variables:
                raise ValueError(f"Missing variable: {key}")
            return variables[key]

        return _VAR_PATTERN.sub(replacer, content)
