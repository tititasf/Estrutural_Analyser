import styles from "./SpecField.module.css";

interface SpecFieldProps {
  chave: string;
  valor: string;
}

function sanitizeValue(raw: string): string {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }

  const str = String(raw).trim();
  if (!str) return "—";

  // Sanitize Python dict syntax if present (e.g. {'laje': 'L301', 'side': 'D'} or {'laje': None})
  if (str.includes("{'") || str.includes('{"')) {
    return str
      .replace(/\{'laje':\s*(?:None|'null'|null),\s*'side':\s*'([^']*)',\s*'face':\s*'([^']*)'[^}]*\}/g, "Face $1 ($2)")
      .replace(/\{'laje':\s*'([^']*)',\s*'side':\s*'([^']*)',\s*'face':\s*'([^']*)'[^}]*\}/g, "$1 (Face $2 - $3)")
      .replace(/\{[^}]+\}/g, "")
      .replace(/,\s*,/g, ",")
      .replace(/^\s*,\s*|\s*,\s*$/g, "")
      .trim() || "—";
  }

  return str;
}

export function SpecField({ chave, valor }: SpecFieldProps) {
  const clean = sanitizeValue(valor);
  const isMultiline = clean.includes("\n");

  return (
    <div className={styles.linha}>
      <span className={styles.chave}>{chave}</span>
      {isMultiline ? (
        <div className={styles.multilineValor}>
          {clean.split("\n").map((part, idx) => (
            <span key={idx} className={styles.multilineItem}>
              {part.trim()}
            </span>
          ))}
        </div>
      ) : (
        <span className={`${styles.valor} tabular-nums`}>{clean}</span>
      )}
    </div>
  );
}
