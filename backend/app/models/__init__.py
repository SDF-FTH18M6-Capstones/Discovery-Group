"""All 13 tables of the approved simple schema."""

from app.models.assets import Asset, Notification, Repair
from app.models.catalogue import Category, Product, Supplier
from app.models.procurement import Purchase, PurchaseItem, Request
from app.models.sales import Sale, SaleItem, StockMovement
from app.models.user import (
    ROLE_CLASSES,
    Admin,
    Employee,
    InventoryManager,
    ProcurementManager,
    SalesAttendant,
    User,
)

_all_ = [
    "ROLE_CLASSES",
    "Admin",
    "Asset",
    "Category",
    "Employee",
    "InventoryManager",
    "Notification",
    "ProcurementManager",
    "Product",
    "Purchase",
    "PurchaseItem",
    "Repair",
    "Request",
    "Sale",
    "SaleItem",
    "SalesAttendant",
    "StockMovement",
    "Supplier",
    "User",
]