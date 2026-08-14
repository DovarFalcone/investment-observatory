from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Security(Base, TimestampMixin):
    __tablename__ = "securities"
    __table_args__ = (UniqueConstraint("canonical_symbol", "exchange", name="uq_security_identity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_symbol: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255))
    asset_type: Mapped[str] = mapped_column(String(32), default="stock")
    exchange: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    provider: Mapped[str] = mapped_column(String(64), default="yahoo_chart")
    provider_symbol: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    list_items: Mapped[list["ListItem"]] = relationship(back_populates="security")
    prices: Mapped[list["PriceObservation"]] = relationship(back_populates="security")
    news_links: Mapped[list["NewsSecurityLink"]] = relationship(back_populates="security")


class UserList(Base):
    __tablename__ = "user_lists"
    __table_args__ = (UniqueConstraint("kind", name="uq_user_list_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["ListItem"]] = relationship(
        back_populates="user_list", cascade="all, delete-orphan", order_by="ListItem.sort_order"
    )


class ListItem(Base):
    __tablename__ = "list_items"
    __table_args__ = (UniqueConstraint("list_id", "security_id", name="uq_list_security"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("user_lists.id", ondelete="CASCADE"), index=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="RESTRICT"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user_list: Mapped[UserList] = relationship(back_populates="items")
    security: Mapped[Security] = relationship(back_populates="list_items")
    holding: Mapped[Optional["HoldingAnnotation"]] = relationship(
        back_populates="list_item", cascade="all, delete-orphan", uselist=False
    )


class HoldingAnnotation(Base):
    __tablename__ = "holding_annotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    list_item_id: Mapped[int] = mapped_column(
        ForeignKey("list_items.id", ondelete="CASCADE"), unique=True
    )
    shares: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    average_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    cost_currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    list_item: Mapped[ListItem] = relationship(back_populates="holding")


class PriceObservation(Base):
    __tablename__ = "price_observations"
    __table_args__ = (
        UniqueConstraint("security_id", "observed_at", "source", name="uq_price_observation"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    session_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    open: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    high: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    low: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    volume: Mapped[Optional[int]] = mapped_column(nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    source: Mapped[str] = mapped_column(String(64))
    source_observed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(16), default="ok")

    security: Mapped[Security] = relationship(back_populates="prices")


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_url: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    group_key: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)

    security_links: Mapped[list["NewsSecurityLink"]] = relationship(
        back_populates="news_item", cascade="all, delete-orphan"
    )


class NewsSecurityLink(Base):
    __tablename__ = "news_security_links"
    __table_args__ = (UniqueConstraint("news_id", "security_id", name="uq_news_security"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_items.id", ondelete="CASCADE"), index=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), index=True)
    relevance: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    news_item: Mapped[NewsItem] = relationship(back_populates="security_links")
    security: Mapped[Security] = relationship(back_populates="news_links")


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_name: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    requested_count: Mapped[int] = mapped_column(default=0)
    completed_count: Mapped[int] = mapped_column(default=0)
    failed_count: Mapped[int] = mapped_column(default=0)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
