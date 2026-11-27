export const ROLE_NAMES = {
  admin: "Administrator",
  procurement: "Procurement Manager",
  inventory: "Inventory Manager",
  sales: "Sales Attendant",
  employee: "Employee",
};

export const ROLES = Object.keys(ROLE_NAMES);

export const STOCK_VIEWERS = ["admin", "inventory"];
export const PROCUREMENT_VIEWERS = ["admin", "procurement"];
export const SALES_VIEWERS = ["admin", "sales"];
export const PURCHASE_VIEWERS = ["admin", "procurement", "inventory"];
