"""Pydantic request/response models for the API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    sku: str = Field(..., description="Stock Keeping Unit identifier for the product.")
    qty: int = Field(..., description="Quantity of the product ordered.")


class OrderRequest(BaseModel):
    customer_id: str = Field(..., description="Unique identifier for the customer placing the order.")
    store_id: str = Field(..., description="Unique identifier for the store where the order is placed.")
    items: list[OrderItem] = Field(..., description="List of items included in the order.")


class ChatMessage(BaseModel):
    customer_id: str = Field(..., description="Unique identifier for the customer sending the message.")
    message: str = Field(..., description="Content of the chat message.")


class ChatStartRequest(BaseModel):
    customer_id: str = Field(..., description="Unique identifier for the customer starting the chat.")
    order_id: str = Field(..., description="Unique identifier for the order associated with the chat.")

