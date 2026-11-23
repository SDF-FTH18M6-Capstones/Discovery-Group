import { useEffect, useState } from "react";

import { api } from "../api/client";
import { useAuth } from "./AuthContext";

let cached = null;

// The signed-in user's business (name, address, receipt footer…), fetched once per visit.
export function useBusiness() {
  const { user } = useAuth();
  const [business, setBusiness] = useState(
    cached && cached.id === user?.business?.id ? cached : user?.business || null,
  );

  useEffect(() => {
    if (!user) return;
    if (cached && cached.id === user.business?.id && cached.name === user.business?.name) {
      setBusiness(cached);
      return;
    }
    api("/api/business")
      .then((data) => {
        cached = data;
        setBusiness(data);
      })
      .catch(() => {});
  }, [user]);

  return business;
}
