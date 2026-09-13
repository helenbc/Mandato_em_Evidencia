import type { Deputy } from "../lib/types";
import { percent } from "../lib/format";
import { ScoreRing } from "./ScoreRing";

type ProfileHeaderProps = {
  deputy: Deputy;
  score: number | null;
};

export function ProfileHeader({ deputy, score }: ProfileHeaderProps) {
  return (
    <div className="profile-head">
      <img className="portrait" src={deputy.photo} alt={`Foto oficial de ${deputy.name}`} />
      <div className="profile-title">
        <span className="profile-party">{deputy.party} · {deputy.uf}</span>
        <h2>{deputy.name}</h2>
        <p>{deputy.hearingCount} audiências · {deputy.opinionCount} opiniões identificadas</p>
      </div>
      <div className="score-block" aria-label={`Alinhamento partidário: ${percent(score)}`}>
        <ScoreRing score={score} />
        <div>
          <strong>Alinhamento partidário</strong>
          <small>
            {deputy.alignment
              ? `${deputy.alignment.comparable_votes} de ${deputy.alignment.recorded_votes} votos comparáveis`
              : "Sem votos no recorte"}
          </small>
        </div>
      </div>
    </div>
  );
}
