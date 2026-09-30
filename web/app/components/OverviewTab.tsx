import type { Deputy } from "../lib/types";
import { percent, stanceLabel } from "../lib/format";

type OverviewTabProps = {
  deputy: Deputy;
  score: number | null;
};

export function OverviewTab({ deputy, score }: OverviewTabProps) {
  return (
    <div className="overview-grid">
      <section className="metric-panel">
        <p className="panel-label">Leitura da métrica</p>
        <h3>{score == null ? "Cobertura insuficiente" : `${percent(score)} dos votos comparáveis seguiram a orientação`}</h3>
        <div className="metric-track" aria-hidden="true">
          <span style={{ width: percent(score ?? 0) }} />
        </div>
        <div className="metric-breakdown">
          <div><strong>{deputy.alignment?.aligned_votes ?? 0}</strong><span>alinhados</span></div>
          <div><strong>{deputy.alignment?.diverged_votes ?? 0}</strong><span>divergentes</span></div>
          <div><strong>{deputy.alignment?.no_orientation ?? 0}</strong><span>sem orientação</span></div>
        </div>
        <p className="coverage-note">
          Cobertura: {percent(deputy.alignment?.coverage)}. Itens sem orientação partidária
          identificável não entram no denominador.
        </p>
      </section>

      <section className="latest-panel">
        <p className="panel-label">Falas em destaque</p>
        {deputy.speeches.length ? deputy.speeches.slice(0, 2).map((speech, index) => (
          <div className="speech-preview" key={`${speech.hearing_id}-${index}`}>
            <div className="speech-meta">
              <span>{speech.subject || "Audiência pública"}</span>
              <span className={`stance ${speech.stance?.toLowerCase()}`}>{stanceLabel[speech.stance || ""] || speech.stance}</span>
            </div>
            <blockquote>“{speech.evidence || speech.question}”</blockquote>
            {speech.status === "pending_llm" && (
              <small>Classificação pendente: a chave da API ainda não foi configurada.</small>
            )}
          </div>
        )) : <p className="empty-state">Não há falas selecionadas para este parlamentar.</p>}
      </section>

      <section className="comparison-panel">
        <p className="panel-label">Fala × voto</p>
        {deputy.comparisons.length ? deputy.comparisons.map((comparison) => (
          <div className="comparison-row" key={comparison.comparison_id}>
            <span>{comparison.tema}</span>
            <strong>{comparison.resultado}</strong>
          </div>
        )) : (
          <div className="pending-comparison">
            <span aria-hidden="true">↔</span>
            <div>
              <strong>Amostra preparada</strong>
              <p>A comparação com a votação do PLP 68/2024 será calculada depois da classificação das falas.</p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
