from dataclasses import dataclass


@dataclass
class Customer:
    name: str
    tier: str


@dataclass
class Order:
    order_id: str
    amount_cents: int


@dataclass
class Invoice:
    invoice_id: str
    order_id: str
    total_cents: int


@dataclass
class Shipment:
    shipment_id: str
    order_id: str
    carrier: str
