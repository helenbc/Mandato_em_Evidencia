export const percent = (value: number | null | undefined) =>
  value == null ? "—" : `${Math.round(value * 100)}%`;

export const stanceLabel: Record<string, string> = {
  FAVORAVEL: "Favorável",
  CONTRARIO: "Contrário",
  MISTO: "Posição mista",
  NAO_DETERMINADO: "Não determinado",
  NAO_CLASSIFICADO: "Aguardando análise",
};

export const statusLabel: Record<string, string> = {
  aligned: "Seguiu o partido",
  diverged: "Divergiu do partido",
  released: "Bancada liberada",
  no_orientation: "Sem orientação identificável",
  ambiguous_orientation: "Orientação ambígua",
  excluded_vote: "Voto fora da métrica",
  excluded_orientation: "Orientação fora da métrica",
};
