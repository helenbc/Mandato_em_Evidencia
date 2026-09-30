import type { Deputy } from "../lib/types";
import { SearchField } from "./SearchField";
import { PartyFilter } from "./PartyFilter";
import { DeputyRow } from "./DeputyRow";
import { MenuIcon } from "./MenuIcon";

type DeputyDirectoryProps = {
  search: string;
  onSearchChange: (value: string) => void;
  party: string;
  parties: string[];
  onPartyChange: (value: string) => void;
  filtered: Deputy[];
  selectedId: number;
  onSelect: (id: number) => void;
  open: boolean;
  onToggle: () => void;
};

export function DeputyDirectory({
  search,
  onSearchChange,
  party,
  parties,
  onPartyChange,
  filtered,
  selectedId,
  onSelect,
  open,
  onToggle,
}: DeputyDirectoryProps) {
  return (
    <aside className={`directory ${open ? "" : "directory-collapsed"}`}>
      <div className="directory-header">
        <button
          type="button"
          className="menu-toggle"
          onClick={onToggle}
          aria-label="Mostrar ou esconder a lista de parlamentares"
          aria-expanded={open}
        >
          <MenuIcon className="menu-toggle-icon" />
        </button>
        {open && <div className="section-kicker">Escolha um parlamentar</div>}
      </div>

      {open && (
        <>
          <SearchField value={search} onChange={onSearchChange} />
          <PartyFilter value={party} parties={parties} onChange={onPartyChange} />
          <div className="directory-count">{filtered.length} resultados</div>
          <div className="deputy-list" role="list">
            {filtered.map((deputy) => (
              <DeputyRow
                key={deputy.id}
                deputy={deputy}
                active={selectedId === deputy.id}
                onSelect={onSelect}
              />
            ))}
            {!filtered.length && <p className="empty-list">Nenhum parlamentar encontrado.</p>}
          </div>
        </>
      )}
    </aside>
  );
}
