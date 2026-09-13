type CurvedArrowProps = {
  className?: string;
};

export function CurvedArrow({ className }: CurvedArrowProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 60 60"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M34 10C28 24 8 22 8 36C8 46 16 48 28 48H44" />
      <path d="M38 42L46 48L38 54" />
    </svg>
  );
}
