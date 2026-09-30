import type { Deputy } from "../lib/types";
import { percent } from "../lib/format";

type DeputyRowProps = {
  deputy: Deputy;
  active: boolean;
  onSelect: (id: number) => void;
};

export function DeputyRow({ deputy, active, onSelect }: DeputyRowProps) {
  return (
    <button
      className={`deputy-row ${active ? "active" : ""}`}
      onClick={() => onSelect(deputy.id)}
      type="button"
      role="listitem"
    >
      <img src={deputy.photo} alt="" />
      <span className="deputy-identity">
        <strong>{deputy.name}</strong>
        <small>{deputy.party} · {deputy.uf}</small>
      </span>
      <span className="row-score">
        {deputy.alignment?.alignment_score == null
          ? <small>sem base</small>
          : percent(deputy.alignment.alignment_score)}
      </span>
    </button>
  );
}
