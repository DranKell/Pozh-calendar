# -*- coding: utf-8 -*-
from sqlalchemy import String, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class WorkType(Base, TimestampMixin):
    __tablename__ = "work_types"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(50), default="")
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100), default="")
    frequency: Mapped[str] = mapped_column(String(50), default="Ежегодно")
    duration_hours: Mapped[float] = mapped_column(Float, default=0)
    price: Mapped[float] = mapped_column(Float, default=0)
    required_cert: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(String(1000), default="")
