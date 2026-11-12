import { configureStore } from "@reduxjs/toolkit";

import { makeResourceSlice } from "./resourceSlice";

export const products = makeResourceSlice("products", "/api/products/");
export const suppliers = makeResourceSlice("suppliers", "/api/suppliers/");
export const categories = makeResourceSlice("categories", "/api/categories/");

export function makeStore() {
  return configureStore({
    reducer: {
      products: products.reducer,
      suppliers: suppliers.reducer,
      categories: categories.reducer,
    },
  });
}