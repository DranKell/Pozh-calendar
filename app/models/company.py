# -*- coding: utf-8 -*-
from typing import Optional
from sqlalchemy import String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    inn: Mapped[str] = mapped_column(String(20), default="")
    kpp: Mapped[str] = mapped_column(String(20), default="")
    ogrn: Mapped[str] = mapped_column(String(30), default="")
    address: Mapped[str] = mapped_column(String(500), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(100), default="")
    bank: Mapped[str] = mapped_column(String(255), default="")
    bik: Mapped[str] = mapped_column(String(20), default="")
    account: Mapped[str] = mapped_column(String(50), default="")
    corr_account: Mapped[str] = mapped_column(String(50), default="")
    director: Mapped[str] = mapped_column(String(255), default="")
    accountant: Mapped[str] = mapped_column(String(255), default="")
    invoice_prefix: Mapped[str] = mapped_column(String(20), default="СЧ")
    vat_rate: Mapped[float] = mapped_column(Float, default=0.0)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
