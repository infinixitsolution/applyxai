from dataclasses import dataclass

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

MAX_PAGE_SIZE = 100


@dataclass
class PageParams:
    page: int
    page_size: int


def page_params(page: int = Query(1, ge=1, le=10_000),
                page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE)) -> PageParams:
    return PageParams(page, page_size)


def paginate(db: Session, stmt: Select, params: PageParams) -> tuple[list, int]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.execute(stmt.limit(params.page_size).offset((params.page - 1) * params.page_size))
    return list(rows.scalars().unique()), total


def page_response(items: list, total: int, params: PageParams) -> dict:
    return {"items": items, "total": total, "page": params.page, "page_size": params.page_size}
