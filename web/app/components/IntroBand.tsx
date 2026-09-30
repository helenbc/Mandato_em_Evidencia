type IntroBandProps = {
  stats: {
    deputies: number;
    recordedVotes: number;
    comparableVotes: number;
    classifiedSpeeches: number;
  };
  scope: string;
  generatedAt: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function IntroBand({ stats, scope, generatedAt, open, onOpenChange }: IntroBandProps) {
  return (
    <section className="intro" aria-label="Sobre este painel">
      <div className="intro-row">
        <div className="intro-text">
          <p className="eyebrow">Transparência parlamentar baseada em evidências</p>
          <h1>Falas, votos nominais e o alinhamento partidário de cada parlamentar — sempre com a fonte à vista.</h1>
        </div>
        <button
          type="button"
          id="metodologia"
          className="intro-toggle"
          aria-expanded={open}
          aria-controls="intro-details"
          onClick={() => onOpenChange(!open)}
        >
          <span className="section-kicker light">Saiba mais</span>
          <span className="intro-chevron" aria-hidden="true">{open ? "−" : "+"}</span>
        </button>
      </div>

      {open && (
        <div className="intro-details" id="intro-details">
          <div className="method-grid">
            <h2>Transparência inclui mostrar os limites.</h2>
            <div>
              <p>
                O alinhamento divide votos iguais à orientação pelos votos em que há orientação
                explícita do partido ou de uma federação reconhecível. Ausências, bancadas liberadas
                e orientações ambíguas ficam fora do cálculo.
              </p>
              <p>
                A análise de falas usa uma LLM com saída estruturada, exige citação literal da
                transcrição e preserva “não determinado” quando a evidência não é suficiente.
                A comparação fala × voto é exploratória, por tema, e não produz nota geral.
              </p>
            </div>
          </div>

          <div className="intro-summary">
            <div className="intro-stats">
              <div><strong>{stats.deputies}</strong><span>parlamentares</span></div>
              <div><strong>{stats.recordedVotes}</strong><span>votos nominais</span></div>
              <div><strong>{stats.comparableVotes}</strong><span>votos comparáveis</span></div>
              <div><strong>{stats.classifiedSpeeches}</strong><span>falas classificadas</span></div>
            </div>
            <p className="intro-scope">{scope}</p>
          </div>

          <div className="source-line">
            <span>Fontes: PublicHearingBR e API de Dados Abertos da Câmara dos Deputados</span>
            <span>Atualizado em {generatedAt}</span>
          </div>
        </div>
      )}
    </section>
  );
}
