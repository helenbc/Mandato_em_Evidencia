import type { Deputy } from "../lib/types";
import { ProfileHeader } from "./ProfileHeader";
import { ProfileTabs, type ProfileTab } from "./ProfileTabs";
import { OverviewTab } from "./OverviewTab";
import { VotesTab } from "./VotesTab";
import { SpeechesTab } from "./SpeechesTab";

type DeputyProfileProps = {
  deputy: Deputy;
  score: number | null;
  tab: ProfileTab;
  onTabChange: (tab: ProfileTab) => void;
};

export function DeputyProfile({ deputy, score, tab, onTabChange }: DeputyProfileProps) {
  return (
    <article className="profile">
      <ProfileHeader deputy={deputy} score={score} />
      <ProfileTabs tab={tab} onChange={onTabChange} />
      {tab === "resumo" && <OverviewTab deputy={deputy} score={score} />}
      {tab === "votos" && <VotesTab deputy={deputy} />}
      {tab === "falas" && <SpeechesTab deputy={deputy} />}
    </article>
  );
}
