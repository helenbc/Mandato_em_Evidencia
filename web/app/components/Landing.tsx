import dashboard from "../dashboard.json";
import { CurvedArrow } from "./CurvedArrow";

type LandingProps = {
  onExploreClick: () => void;
};

export function Landing({ onExploreClick }: LandingProps) {
  const generated = new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "America/Fortaleza",
  }).format(new Date(dashboard.generatedAt));

  return (
    <main className="landing-screen">
      <header className="site-header">
        <span className="brand">
          <span className="brand-mark" aria-hidden="true">ME</span>
          <span>Mandato em Evidência</span>
        </span>
        <button type="button" className="landing-corner-link" onClick={onExploreClick}>
          <span>Ir para a ferramenta</span>
          <CurvedArrow className="landing-corner-arrow" />
        </button>
      </header>

      <div className="landing-split">
        <div className="landing-split-left">
          <p className="eyebrow">Transparência parlamentar baseada em evidências</p>
          <h1>O que foi dito.<br /><em>O que foi votado.</em></h1>
          <div className="landing-visual-placeholder" aria-hidden="true">
            <span>imagem em definição</span>
          </div>

          <div className="landing-stats-mini">
            <div><strong>{dashboard.stats.deputies}</strong><span>parlamentares</span></div>
            <div><strong>{dashboard.stats.recordedVotes}</strong><span>votos nominais</span></div>
            <div><strong>{dashboard.stats.comparableVotes}</strong><span>votos comparáveis</span></div>
            <div><strong>{dashboard.stats.classifiedSpeeches}</strong><span>falas classificadas</span></div>
          </div>
          <p className="landing-scope">
            Recorte atual: votações do Plenário em 10 de julho de 2024 e falas do PublicHearingBR.
          </p>
        </div>

        <div className="landing-split-right">
          <p className="eyebrow">Como funciona</p>
          <p className="landing-explanation">
            O Mandato em Evidência cruza as falas em audiências públicas com os
            votos nominais no plenário, pra mostrar, com fonte, se o que foi dito
            bate com o que foi votado. Sem ranking, sem recomendação de voto,
            cada posição exige citação literal da transcrição, e cada voto linka
            direto pra fonte oficial da Câmara.
          </p>

          <p className="eyebrow landing-limits-kicker">Os limites, ditos com clareza</p>
          <p className="landing-explanation">
            O alinhamento divide votos iguais à orientação pelos votos em que há
            orientação explícita do partido ou de uma federação reconhecível.
            Ausências, bancadas liberadas e orientações ambíguas ficam fora do
            cálculo. A análise de falas exige citação literal da transcrição e
            preserva “não determinado” quando a evidência não é suficiente.
          </p>

          <p className="landing-source">
            Fontes: PublicHearingBR e API de Dados Abertos da Câmara dos Deputados
            · Atualizado em {generated}
          </p>
        </div>
      </div>
    </main>
  );
}
