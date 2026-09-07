# -*- coding: utf-8 -*-
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Object(Base, TimestampMixin):
    __tablename__ = "objects"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(255), default="")
    inn: Mapped[str] = mapped_column(String(20), default="")
    contact_person: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    functional_hazard: Mapped[str] = mapped_column(String(50), default="Ф3.1")
    fire_hazard_category: Mapped[str] = mapped_column(String(50), default="В")
    construction_hazard: Mapped[str] = mapped_column(String(50), default="С0")
    total_area: Mapped[float] = mapped_column(default=0.0)
    floors: Mapped[int] = mapped_column(default=1)
    risk_level: Mapped[str] = mapped_column(String(50), default="")
    status: Mapped[str] = mapped_column(String(50), default="Активен")
    delete_reason: Mapped[str] = mapped_column(String(500), nullable=True)
    notes: Mapped[str] = mapped_column(String(1000), default="")

