type PartyFilterProps = {
  value: string;
  parties: string[];
  onChange: (value: string) => void;
};

export function PartyFilter({ value, parties, onChange }: PartyFilterProps) {
  return (
    <label className="party-field">
      <span>Partido</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="TODOS">Todos</option>
        {parties.map((item) => <option key={item}>{item}</option>)}
      </select>
    </label>
  );
}
