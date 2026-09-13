import { CurvedArrow } from "./CurvedArrow";

type SiteHeaderProps = {
  onBrandClick: () => void;
  onMethodologyClick: () => void;
};

export function SiteHeader({ onBrandClick, onMethodologyClick }: SiteHeaderProps) {
  return (
    <header className="site-header">
      <div className="header-start">
        <button
          type="button"
          className="brand"
          onClick={onBrandClick}
          aria-label="Mandato em Evidência — página inicial"
        >
          <span className="brand-mark" aria-hidden="true">ME</span>
          <span>Mandato em Evidência</span>
        </button>
        <button type="button" className="tool-back-link" onClick={onBrandClick}>
          <CurvedArrow className="tool-back-arrow" />
          <span>Voltar</span>
        </button>
      </div>
      <nav aria-label="Navegação principal">
        <a href="#explorar">Explorar</a>
        <a href="#metodologia" onClick={onMethodologyClick}>Metodologia</a>
        <span className="data-badge">Dados experimentais</span>
      </nav>
    </header>
  );
}
