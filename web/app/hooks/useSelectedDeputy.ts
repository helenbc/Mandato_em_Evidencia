import { useState } from "react";
import type { Deputy } from "../lib/types";

export function useSelectedDeputy(deputies: Deputy[]) {
  const initial = deputies.find((deputy) => deputy.alignment?.alignment_score != null) ?? deputies[0];
  const [selectedId, setSelectedId] = useState(initial.id);
  const selected = deputies.find((deputy) => deputy.id === selectedId) ?? initial;

  return { selected, selectedId, setSelectedId };
}
