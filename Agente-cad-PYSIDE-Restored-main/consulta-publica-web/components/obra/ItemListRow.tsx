import { ChevronRight } from "lucide-react";
import { TypeIcon, type TipoElemento } from "@/components/ui/TypeIcon";
import type { ObraItem } from "@/lib/api/obra";
import styles from "./ItemListRow.module.css";

function ehTipoElemento(tipo: string): tipo is TipoElemento {
  return tipo === "pilar" || tipo === "viga_fundo" || tipo === "viga_lateral" || tipo === "laje";
}

interface ItemListRowProps {
  item: ObraItem;
  onSelecionar: (code: string) => void;
}

/** Linha de item no Índice de Obra — 56px, ícone de tipo + título; nunca
 * expõe `item_id`/`pavimento` cru (só `code`/`titulo`/`tipo`, AC6). */
export function ItemListRow({ item, onSelecionar }: ItemListRowProps) {
  return (
    <button type="button" className={styles.linha} onClick={() => onSelecionar(item.code)}>
      {ehTipoElemento(item.tipo) && <TypeIcon tipo={item.tipo} />}
      <span className={styles.titulo}>{item.titulo}</span>
      <ChevronRight size={20} className={styles.seta} aria-hidden="true" />
    </button>
  );
}
