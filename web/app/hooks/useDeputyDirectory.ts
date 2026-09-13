import { useMemo, useState } from "react";
import type { Deputy } from "../lib/types";

export function useDeputyDirectory(deputies: Deputy[]) {
  const [search, setSearch] = useState("");
  const [party, setParty] = useState("TODOS");

  const parties = useMemo(
    () => Array.from(new Set(deputies.map((deputy) => deputy.party))).sort(),
    [deputies],
  );

  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("pt-BR");
    return deputies.filter(
      (deputy) =>
        (party === "TODOS" || deputy.party === party) &&
        (!query || deputy.name.toLocaleLowerCase("pt-BR").includes(query)),
    );
  }, [deputies, party, search]);

  return { search, setSearch, party, setParty, parties, filtered };
}
