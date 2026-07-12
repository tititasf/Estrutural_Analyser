"use client";

import { Segmented, type SegmentedOption } from "@/components/ui/Segmented";

export type FichaTabValue = "n1" | "n3" | "paineis";

interface FichaTabsProps {
  temN1: boolean;
  temN3: boolean;
  temLv: boolean;
  aba: FichaTabValue;
  onSelecionar: (aba: FichaTabValue) => void;
}

/** Abas dinâmicas da Ficha (§5.3) — só aparecem as que têm dado; se sobra
 * só 1, o `Segmented` já colapsa sozinho para rótulo estático (AC2). */
export function FichaTabs({ temN1, temN3, temLv, aba, onSelecionar }: FichaTabsProps) {
  const opcoes: SegmentedOption[] = [
    ...(temN1 ? [{ value: "n1", label: "N1" }] : []),
    ...(temN3 ? [{ value: "n3", label: "N3" }] : []),
    ...(temLv ? [{ value: "paineis", label: "PAINÉIS" }] : []),
  ];

  return (
    <Segmented
      options={opcoes}
      selected={aba}
      onSelect={(valor) => onSelecionar(valor as FichaTabValue)}
      label="Visualização do item"
    />
  );
}
