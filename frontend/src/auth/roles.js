export const ROLE_NAMES = {
  admin: "Administrator",
  procurement: "Procurement Manager",
  inventory: "Inventory Manager",
  sales: "Sales Attendant",
  employee: "Employee",
};

export const ROLES = Object.keys(ROLE_NAMES);

export const STOCK_MANAGERS = ["admin", "inventory"]; // products, categories, assets
export const PROCUREMENT = ["admin", "procurement"]; // suppliers, every request
