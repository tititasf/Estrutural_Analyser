"use client";

import { useRef } from "react";
import styles from "./CodeInput.module.css";

interface CodeInputProps {
  value: string;
  onChange: (novoValor: string) => void;
  onSubmit?: () => void;
  id?: string;
  label: string;
}

/** Campo de código — mono 22px, atributos de teclado que evitam
 * autocorreção/autocapitalização (base62 é case-sensitive), botão limpar
 * (⌫) embutido. Alvo tocável do botão limpar ≥56px (AC12). */
export function CodeInput({ value, onChange, onSubmit, id = "code-input", label }: CodeInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className={styles.wrapper}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <div className={styles.inputRow}>
        <input
          ref={inputRef}
          id={id}
          type="text"
          inputMode="text"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          autoComplete="off"
          className={styles.input}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSubmit?.();
          }}
          placeholder="aF3kZ9xQ2m"
          aria-label={label}
        />
        {value.length > 0 && (
          <button
            type="button"
            className={styles.clearButton}
            onClick={() => {
              onChange("");
              inputRef.current?.focus();
            }}
            aria-label="Limpar código"
          >
            ⌫
          </button>
        )}
      </div>
    </div>
  );
}
