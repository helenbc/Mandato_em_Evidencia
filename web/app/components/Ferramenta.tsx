// O dashboard é gerado pelo comando `ideias-em-rede web-data`. Mantê-lo como
// artefato estático torna a interface reproduzível e dispensa um backend web.

import { useState } from "react";
import dashboard from "../dashboard.json";
import { deputies, scopeText, stats } from "../lib/deputies";
import { useDeputyDirectory } from "../hooks/useDeputyDirectory";
import { useSelectedDeputy } from "../hooks/useSelectedDeputy";
import { SiteHeader } from "./SiteHeader";
import { IntroBand } from "./IntroBand";
import { DeputyDirectory } from "./DeputyDirectory";
import { DeputyProfile } from "./DeputyProfile";
import type { ProfileTab } from "./ProfileTabs";

type FerramentaProps = {
  onBackToLanding: () => void;
};

export function Ferramenta({ onBackToLanding }: FerramentaProps) {
  const { selected, selectedId, setSelectedId } = useSelectedDeputy(deputies);
  const { search, setSearch, party, setParty, parties, filtered } = useDeputyDirectory(deputies);
  const [tab, setTab] = useState<ProfileTab>("resumo");
  const [methodologyOpen, setMethodologyOpen] = useState(false);
  const [directoryOpen, setDirectoryOpen] = useState(true);

  const score = selected.alignment?.alignment_score ?? null;
  const generated = new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "America/Fortaleza",
  }).format(new Date(dashboard.generatedAt));

  return (
    <main>
      <SiteHeader
        onBrandClick={onBackToLanding}
        onMethodologyClick={() => setMethodologyOpen(true)}
      />

      <section className={`explorer ${directoryOpen ? "" : "explorer-collapsed"}`} id="explorar">
        <DeputyDirectory
          search={search}
          onSearchChange={setSearch}
          party={party}
          parties={parties}
          onPartyChange={setParty}
          filtered={filtered}
          selectedId={selectedId}
          onSelect={setSelectedId}
          open={directoryOpen}
          onToggle={() => setDirectoryOpen((value) => !value)}
        />
        <DeputyProfile deputy={selected} score={score} tab={tab} onTabChange={setTab} />
      </section>

      <IntroBand
        stats={stats}
        scope={scopeText}
        generatedAt={generated}
        open={methodologyOpen}
        onOpenChange={setMethodologyOpen}
      />
    </main>
  );
}
