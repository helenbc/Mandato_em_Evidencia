export type ProfileTab = "resumo" | "votos" | "falas";

const TAB_LABELS: Record<ProfileTab, string> = {
  resumo: "Visão geral",
  votos: "Votos",
  falas: "Falas",
};

type ProfileTabsProps = {
  tab: ProfileTab;
  onChange: (tab: ProfileTab) => void;
};

export function ProfileTabs({ tab, onChange }: ProfileTabsProps) {
  return (
    <div className="tabs" role="tablist" aria-label="Dados do parlamentar">
      {(Object.keys(TAB_LABELS) as ProfileTab[]).map((item) => (
        <button
          key={item}
          type="button"
          role="tab"
          aria-selected={tab === item}
          className={tab === item ? "active" : ""}
          onClick={() => onChange(item)}
        >
          {TAB_LABELS[item]}
        </button>
      ))}
    </div>
  );
}
