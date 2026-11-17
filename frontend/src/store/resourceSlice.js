import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

import { api } from "../api/client";

export function makeResourceSlice(name, path) {
  const fetchList = createAsyncThunk(
    `${name}/fetchList`,
    async (params = {}, { rejectWithValue }) => {
      const query = new URLSearchParams(
        Object.entries(params).filter(([, value]) => value !== "" && value != null),
      );
      try {
        return await api(`${path}?${query}`);
      } catch (error) {
        return rejectWithValue(error.message);
      }
    },
  );

  const saveItem = createAsyncThunk(`${name}/save`, async ({ id, data }, { rejectWithValue }) => {
    try {
      return await api(id ? `${path}${id}` : path, { method: id ? "PUT" : "POST", body: data });
    } catch (error) {
      return rejectWithValue({ message: error.message, details: error.details || {} });
    }
  });

  const deleteItem = createAsyncThunk(`${name}/delete`, async (id, { rejectWithValue }) => {
    try {
      await api(`${path}${id}`, { method: "DELETE" });
      return id;
    } catch (error) {
      return rejectWithValue(error.message);
    }
  });

  const slice = createSlice({
    name,
    initialState: { items: [], count: 0, page: 1, pages: 0, status: "idle", error: null },
    reducers: {
      patchItem(state, { payload: { id, changes } }) {
        const item = state.items.find((row) => row.id === id);
        if (item) Object.assign(item, changes);
      },
      removeItem(state, { payload: id }) {
        const before = state.items.length;
        state.items = state.items.filter((row) => row.id !== id);
        if (state.items.length < before) state.count -= 1;
      },
      restoreItems(state, { payload: { items, count } }) {
        state.items = items;
        state.count = count;
      },
    },
    extraReducers: (builder) => {
      builder
        .addCase(fetchList.pending, (state) => {
          state.status = "loading";
          state.error = null;
        })
        .addCase(fetchList.fulfilled, (state, { payload }) => {
          state.status = "ready";
          state.items = payload.results;
          state.count = payload.count;
          state.page = payload.page;
          state.pages = payload.pages;
        })
        .addCase(fetchList.rejected, (state, { payload }) => {
          state.status = "failed";
          state.error = payload;
        })
        .addCase(deleteItem.rejected, (state, { payload }) => {
          state.error = payload;
        });
    },
  });

  return { reducer: slice.reducer, actions: slice.actions, fetchList, saveItem, deleteItem };
}
