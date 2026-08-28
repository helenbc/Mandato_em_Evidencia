"use client";

// O dashboard é gerado pelo comando `ideias-em-rede web-data`. Mantê-lo como
// artefato estático torna a interface reproduzível e dispensa um backend web.

import { useMemo, useState } from "react";
import dashboard from "./dashboard.json";

type Alignment = {
  recorded_votes: number;
  comparable_votes: number;
  aligned_votes: number;
  diverged_votes: number;
  no_orientation: number;
  alignment_score: number | null;
  coverage: number;
};

type VoteDetail = {
  votacao_id: string;
  data: string | null;
  descricao: string | null;
  votacao_uri: string | null;
  voto_original: string | null;
  orientacao: string | null;
  orientacao_fonte: string | null;
  status: string;
};

type Speech = {
  status: string;
  subject: string | null;
  topic: string | null;
  question: string | null;
  stance: string | null;
  evidence: string | null;
  confidence: number | null;
  hearing_id: number | null;
  model: string | null;
};

type Comparison = {
  comparison_id: string;
  tema: string;
  posicao_fala: string;
  voto: string;
  resultado: string;
  evidencia_fala: string;
};

type Deputy = {
  id: number;
  name: string;
  party: string;
  uf: string;
  photo: string;
  hearingCount: number;
  opinionCount: number;
  alignment: Alignment | null;
  alignmentDetails: VoteDetail[];
  speeches: Speech[];
  comparisons: Comparison[];
};

const deputies = dashboard.deputies as Deputy[];

const percent = (value: number | null | undefined) =>
  value == null ? "—" : `${Math.round(value * 100)}%`;

const stanceLabel: Record<string, string> = {
  FAVORAVEL: "Favorável",
  CONTRARIO: "Contrário",
  MISTO: "Posição mista",
  NAO_DETERMINADO: "Não determinado",
  NAO_CLASSIFICADO: "Aguardando análise",
};

const statusLabel: Record<string, string> = {
  aligned: "Seguiu o partido",
  diverged: "Divergiu do partido",
  released: "Bancada liberada",
  no_orientation: "Sem orientação identificável",
  ambiguous_orientation: "Orientação ambígua",
  excluded_vote: "Voto fora da métrica",
  excluded_orientation: "Orientação fora da métrica",
};

export default function Home() {
  const initial = deputies.find((deputy) => deputy.alignment?.alignment_score != null) ?? deputies[0];
  const [selectedId, setSelectedId] = useState(initial.id);
  const [search, setSearch] = useState("");
  const [party, setParty] = useState("TODOS");
  const [tab, setTab] = useState<"resumo" | "votos" | "falas">("resumo");

  const parties = useMemo(
    () => Array.from(new Set(deputies.map((deputy) => deputy.party))).sort(),
    [],
  );
  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("pt-BR");
    return deputies.filter(
      (deputy) =>
        (party === "TODOS" || deputy.party === party) &&
        (!query || deputy.name.toLocaleLowerCase("pt-BR").includes(query)),
    );
  }, [party, search]);
  const selected = deputies.find((deputy) => deputy.id === selectedId) ?? initial;
  const score = selected.alignment?.alignment_score ?? null;
  const generated = new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "America/Fortaleza",
  }).format(new Date(dashboard.generatedAt));

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="Mandato em Evidência — início">
          <span className="brand-mark" aria-hidden="true">ME</span>
          <span>Mandato em Evidência</span>
        </a>
        <nav aria-label="Navegação principal">
          <a href="#explorar">Explorar</a>
          <a href="#metodologia">Metodologia</a>
          <span className="data-badge">Dados experimentais</span>
        </nav>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow">Transparência parlamentar baseada em evidências</p>
          <h1>O que foi dito.<br /><em>O que foi votado.</em></h1>
          <p className="hero-lead">
            Consulte falas em audiências públicas, votos nominais e o alinhamento de cada
            parlamentar com a orientação do partido — sempre com a fonte à vista.
          </p>
        </div>
        <aside className="hero-note" aria-label="Escopo atual da análise">
          <span className="note-number">01</span>
          <div>
            <strong>Recorte atual</strong>
            <p>Votações do Plenário em 10 de julho de 2024 e falas do PublicHearingBR.</p>
          </div>
        </aside>
      </section>

      <section className="stats-band" aria-label="Resumo da base analisada">
        <div><strong>{dashboard.stats.deputies}</strong><span>parlamentares localizados</span></div>
        <div><strong>{dashboard.stats.recordedVotes}</strong><span>votos nominais</span></div>
        <div><strong>{dashboard.stats.comparableVotes}</strong><span>votos comparáveis</span></div>
        <div><strong>{dashboard.stats.classifiedSpeeches}</strong><span>falas classificadas</span></div>
      </section>

      <section className="explorer" id="explorar">
        <aside className="directory">
          <div className="section-kicker"><span>02</span> Escolha um parlamentar</div>
          <label className="search-field">
            <span aria-hidden="true">⌕</span>
            <span className="sr-only">Buscar parlamentar</span>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Buscar por nome"
            />
          </label>
          <label className="party-field">
            <span>Partido</span>
            <select value={party} onChange={(event) => setParty(event.target.value)}>
              <option value="TODOS">Todos</option>
              {parties.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
          <div className="directory-count">{filtered.length} resultados</div>
          <div className="deputy-list" role="list">
            {filtered.map((deputy) => (
              <button
                className={`deputy-row ${selected.id === deputy.id ? "active" : ""}`}
                key={deputy.id}
                onClick={() => setSelectedId(deputy.id)}
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
            ))}
            {!filtered.length && <p className="empty-list">Nenhum parlamentar encontrado.</p>}
          </div>
        </aside>

        <article className="profile">
          <div className="profile-head">
            <img className="portrait" src={selected.photo} alt={`Foto oficial de ${selected.name}`} />
            <div className="profile-title">
              <span className="profile-party">{selected.party} · {selected.uf}</span>
              <h2>{selected.name}</h2>
              <p>{selected.hearingCount} audiências · {selected.opinionCount} opiniões identificadas</p>
            </div>
            <div className="score-block" aria-label={`Alinhamento partidário: ${percent(score)}`}>
              <div
                className="score-ring"
                style={{ "--score": `${(score ?? 0) * 360}deg` } as React.CSSProperties}
              >
                <span>{percent(score)}</span>
              </div>
              <div>
                <strong>Alinhamento partidário</strong>
                <small>
                  {selected.alignment
                    ? `${selected.alignment.comparable_votes} de ${selected.alignment.recorded_votes} votos comparáveis`
                    : "Sem votos no recorte"}
                </small>
              </div>
            </div>
          </div>

          <div className="tabs" role="tablist" aria-label="Dados do parlamentar">
            {(["resumo", "votos", "falas"] as const).map((item) => (
              <button
                key={item}
                type="button"
                role="tab"
                aria-selected={tab === item}
                className={tab === item ? "active" : ""}
                onClick={() => setTab(item)}
              >
                {item === "resumo" ? "Visão geral" : item === "votos" ? "Votos" : "Falas"}
              </button>
            ))}
          </div>

          {tab === "resumo" && (
            <div className="overview-grid">
              <section className="metric-panel">
                <p className="panel-label">Leitura da métrica</p>
                <h3>{score == null ? "Cobertura insuficiente" : `${percent(score)} dos votos comparáveis seguiram a orientação`}</h3>
                <div className="metric-track" aria-hidden="true">
                  <span style={{ width: percent(score ?? 0) }} />
                </div>
                <div className="metric-breakdown">
                  <div><strong>{selected.alignment?.aligned_votes ?? 0}</strong><span>alinhados</span></div>
                  <div><strong>{selected.alignment?.diverged_votes ?? 0}</strong><span>divergentes</span></div>
                  <div><strong>{selected.alignment?.no_orientation ?? 0}</strong><span>sem orientação</span></div>
                </div>
                <p className="coverage-note">
                  Cobertura: {percent(selected.alignment?.coverage)}. Itens sem orientação partidária
                  identificável não entram no denominador.
                </p>
              </section>

              <section className="latest-panel">
                <p className="panel-label">Falas em destaque</p>
                {selected.speeches.length ? selected.speeches.slice(0, 2).map((speech, index) => (
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
                {selected.comparisons.length ? selected.comparisons.map((comparison) => (
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
          )}

          {tab === "votos" && (
            <section className="detail-section">
              <div className="detail-intro">
                <div><p className="panel-label">Registro nominal</p><h3>{selected.alignmentDetails.length} votos no recorte</h3></div>
                <p>Compare o voto registrado com a orientação partidária que pôde ser identificada.</p>
              </div>
              <div className="vote-list">
                {selected.alignmentDetails.map((vote) => (
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
          )}

          {tab === "falas" && (
            <section className="detail-section">
              <div className="detail-intro">
                <div><p className="panel-label">Audiências públicas</p><h3>Posições extraídas das falas</h3></div>
                <p>Cada posição só é aceita quando a evidência citada existe literalmente na transcrição.</p>
              </div>
              <div className="speech-list">
                {selected.speeches.map((speech, index) => (
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
                {!selected.speeches.length && <p className="empty-state">Nenhuma fala selecionada neste recorte.</p>}
              </div>
            </section>
          )}
        </article>
      </section>

      <section className="methodology" id="metodologia">
        <div className="section-kicker light"><span>03</span> Como interpretar</div>
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
        <div className="source-line">
          <span>Fontes: PublicHearingBR e API de Dados Abertos da Câmara dos Deputados</span>
          <span>Atualizado em {generated}</span>
        </div>
      </section>
    </main>
  );
}
