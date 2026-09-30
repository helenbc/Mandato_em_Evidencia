import dashboard from "../dashboard.json";
import type { Deputy } from "./types";

export const deputies = (dashboard.deputies as Deputy[]).filter(
  (deputy) => deputy.alignment?.alignment_score != null,
);

const sumAlignment = (field: "recorded_votes" | "comparable_votes") =>
  deputies.reduce((total, deputy) => total + (deputy.alignment?.[field] ?? 0), 0);

export const stats = {
  deputies: deputies.length,
  recordedVotes: sumAlignment("recorded_votes"),
  comparableVotes: sumAlignment("comparable_votes"),
  classifiedSpeeches: dashboard.stats.classifiedSpeeches,
};

type Collection = {
  period?: { start?: string; end?: string };
  organ_filter?: string;
};

const ORGAN_NAMES: Record<string, string> = { PLEN: "Plenário" };

// timeZone UTC evita que "2024-07-10" vire dia 9 em fusos atrás de Greenwich.
const formatDate = (iso: string) =>
  new Intl.DateTimeFormat("pt-BR", { dateStyle: "long", timeZone: "UTC" }).format(new Date(iso));

function buildScopeText(collection: Collection): string {
  const { period, organ_filter: organ } = collection;
  if (!period?.start || !period.end) return "Recorte atual: falas do PublicHearingBR.";

  const when =
    period.start === period.end
      ? `em ${formatDate(period.start)}`
      : `de ${formatDate(period.start)} a ${formatDate(period.end)}`;
  const where = organ ? ` ${ORGAN_NAMES[organ] ? `do ${ORGAN_NAMES[organ]}` : `do órgão ${organ}`}` : "";

  return `Recorte atual: votações${where} ${when} e falas do PublicHearingBR.`;
}

export const scopeText = buildScopeText(dashboard.collection as Collection);
