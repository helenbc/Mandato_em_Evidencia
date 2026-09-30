type SearchFieldProps = {
  value: string;
  onChange: (value: string) => void;
};

export function SearchField({ value, onChange }: SearchFieldProps) {
  return (
    <label className="search-field">
      <span aria-hidden="true">⌕</span>
      <span className="sr-only">Buscar parlamentar</span>
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Buscar por nome"
      />
    </label>
  );
}
