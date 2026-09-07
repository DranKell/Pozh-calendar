# -*- coding: utf-8 -*-
from datetime import datetime, date as date_type
from typing import Optional

from sqlalchemy import String, Float, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    date: Mapped[date_type] = mapped_column(Date, index=True)
    due_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)
    object_id: Mapped[str] = mapped_column(String(50), ForeignKey("objects.id"), index=True)
    company_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("companies.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="Выставлен")
    subtotal: Mapped[float] = mapped_column(Float, default=0)
    vat_rate: Mapped[float] = mapped_column(Float, default=0)
    vat_amount: Mapped[float] = mapped_column(Float, default=0)
    total: Mapped[float] = mapped_column(Float, default=0)
    paid_amount: Mapped[float] = mapped_column(Float, default=0)
    paid_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)
    payment_ref: Mapped[str] = mapped_column(String(255), default="")
    payment_purpose: Mapped[str] = mapped_column(String(1000), default="")
    notes: Mapped[str] = mapped_column(String(1000), default="")


class InvoiceItem(Base, TimestampMixin):
    __tablename__ = "invoice_items"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    invoice_id: Mapped[str] = mapped_column(String(50), ForeignKey("invoices.id"), index=True)
    assignment_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    work_type_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(String(1000), default="")
    quantity: Mapped[float] = mapped_column(Float, default=1)
    unit: Mapped[str] = mapped_column(String(50), default="усл.")
    price: Mapped[float] = mapped_column(Float, default=0)
    amount: Mapped[float] = mapped_column(Float, default=0)
