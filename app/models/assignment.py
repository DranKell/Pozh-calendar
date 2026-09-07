# -*- coding: utf-8 -*-
from datetime import date as date_type, datetime
from typing import Optional

from sqlalchemy import String, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Assignment(Base, TimestampMixin):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    object_id: Mapped[str] = mapped_column(String(50), ForeignKey("objects.id"), index=True)
    work_type_id: Mapped[str] = mapped_column(String(50), ForeignKey("work_types.id"), index=True)
    frequency: Mapped[str] = mapped_column(String(50), default="Разовая")
    start_date: Mapped[date_type] = mapped_column(Date)
    end_date: Mapped[date_type] = mapped_column(Date)
    price_per_unit: Mapped[float] = mapped_column(Float, default=0)
    total_price: Mapped[float] = mapped_column(Float, default=0)
    paid_amount: Mapped[float] = mapped_column(Float, default=0)
    responsible: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(50), default="Активно")
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(String(1000), default="")
