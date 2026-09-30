export type Alignment = {
  recorded_votes: number;
  comparable_votes: number;
  aligned_votes: number;
  diverged_votes: number;
  no_orientation: number;
  alignment_score: number | null;
  coverage: number;
};

export type VoteDetail = {
  votacao_id: string;
  data: string | null;
  descricao: string | null;
  votacao_uri: string | null;
  voto_original: string | null;
  orientacao: string | null;
  orientacao_fonte: string | null;
  status: string;
};

export type Speech = {
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

export type Comparison = {
  comparison_id: string;
  tema: string;
  posicao_fala: string;
  voto: string;
  resultado: string;
  evidencia_fala: string;
};

export type Deputy = {
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
