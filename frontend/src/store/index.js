import { configureStore } from "@reduxjs/toolkit";

import { makeResourceSlice } from "./resourceSlice";

export const products = makeResourceSlice("products", "/api/products/");
export const suppliers = makeResourceSlice("suppliers", "/api/suppliers/");
export const categories = makeResourceSlice("categories", "/api/categories/");
export const requests = makeResourceSlice("requests", "/api/requests/");
export const assets = makeResourceSlice("assets", "/api/assets/");
export const users = makeResourceSlice("users", "/api/users/");
export const sales = makeResourceSlice("sales", "/api/sales/");
export const purchases = makeResourceSlice("purchases", "/api/purchases/");
export const movements = makeResourceSlice("movements", "/api/stock/movements");
export const repairs = makeResourceSlice("repairs", "/api/repairs/");
export const notifications = makeResourceSlice("notifications", "/api/notifications/");

export function makeStore() {
  return configureStore({
    reducer: {
      products: products.reducer,
      suppliers: suppliers.reducer,
      categories: categories.reducer,
      requests: requests.reducer,
      assets: assets.reducer,
      users: users.reducer,
      sales: sales.reducer,
      purchases: purchases.reducer,
      movements: movements.reducer,
      repairs: repairs.reducer,
      notifications: notifications.reducer,
    },
  });
}