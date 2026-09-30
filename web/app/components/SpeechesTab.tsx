import type { Deputy } from "../lib/types";
import { percent, stanceLabel } from "../lib/format";

type SpeechesTabProps = {
  deputy: Deputy;
};

export function SpeechesTab({ deputy }: SpeechesTabProps) {
  return (
    <section className="detail-section">
      <div className="detail-intro">
        <div><p className="panel-label">Audiências públicas</p><h3>Posições extraídas das falas</h3></div>
        <p>Cada posição só é aceita quando a evidência citada existe literalmente na transcrição.</p>
      </div>
      <div className="speech-list">
        {deputy.speeches.map((speech, index) => (
          <article className="speech-item" key={`${speech.hearing_id}-${index}`}>
            <div className="speech-meta">
              <span>Audiência {speech.hearing_id} · {speech.subject}</span>
              <span className={`stance ${speech.stance?.toLowerCase()}`}>{stanceLabel[speech.stance || ""] || speech.stance}</span>
            </div>
            <h4>{speech.topic || "Tema aguardando classificação"}</h4>
            <p className="speech-question">{speech.question}</p>
            <blockquote>“{speech.evidence}”</blockquote>
            <footer>
              {speech.confidence == null ? "Processamento LLM pendente" : `Confiança: ${percent(speech.confidence)}`}
            </footer>
          </article>
        ))}
        {!deputy.speeches.length && <p className="empty-state">Nenhuma fala selecionada neste recorte.</p>}
      </div>
    </section>
  );
}
