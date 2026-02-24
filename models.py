"""Pydantic request/response models for the API."""

from __future__ import annotations

from pydantic import BaseModel


class OrderItem(BaseModel):
    sku: str
    qty: int


class OrderRequest(BaseModel):
    customer_id: str
    store_id: str
    items: list[OrderItem]


class ChatMessage(BaseModel):
    customer_id: str
    message: str


class ChatStartRequest(BaseModel):
    customer_id: str
    order_id: str
