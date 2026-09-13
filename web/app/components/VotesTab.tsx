import type { Deputy } from "../lib/types";
import { statusLabel } from "../lib/format";

type VotesTabProps = {
  deputy: Deputy;
};

export function VotesTab({ deputy }: VotesTabProps) {
  return (
    <section className="detail-section">
      <div className="detail-intro">
        <div><p className="panel-label">Registro nominal</p><h3>{deputy.alignmentDetails.length} votos no recorte</h3></div>
        <p>Compare o voto registrado com a orientação partidária que pôde ser identificada.</p>
      </div>
      <div className="vote-list">
        {deputy.alignmentDetails.map((vote) => (
          <article className="vote-item" key={vote.votacao_id}>
            <div className={`status-dot ${vote.status}`} aria-hidden="true" />
            <div>
              <div className="vote-title"><strong>{statusLabel[vote.status] || vote.status}</strong><span>{vote.data}</span></div>
              <p>{vote.descricao}</p>
              <div className="vote-values">
                <span>Voto <strong>{vote.voto_original || "—"}</strong></span>
                <span>Orientação <strong>{vote.orientacao || "não identificada"}</strong></span>
                {vote.votacao_uri && <a href={vote.votacao_uri} target="_blank" rel="noreferrer">Ver fonte ↗</a>}
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
