"use client";

import { useState } from "react";
import { Landing } from "./components/Landing";
import { Ferramenta } from "./components/Ferramenta";

type View = "landing" | "ferramenta";

export default function Home() {
  const [view, setView] = useState<View>("landing");

  if (view === "ferramenta") {
    return <Ferramenta onBackToLanding={() => setView("landing")} />;
  }

  return <Landing onExploreClick={() => setView("ferramenta")} />;
}
