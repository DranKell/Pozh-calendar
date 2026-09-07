# -*- coding: utf-8 -*-
from datetime import datetime, date as date_type
from typing import Optional

from sqlalchemy import String, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Execution(Base, TimestampMixin):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String(50), ForeignKey("assignments.id"), index=True)
    object_id: Mapped[str] = mapped_column(String(50), ForeignKey("objects.id"), index=True)
    work_type_id: Mapped[str] = mapped_column(String(50), ForeignKey("work_types.id"), index=True)
    planned_date: Mapped[date_type] = mapped_column(Date, index=True)
    actual_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Запланировано")
    performed_by: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(String(1000), default="")
