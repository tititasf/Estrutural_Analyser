"use client";

import { useEffect, useState } from "react";
import { Printer } from "lucide-react";
import QRCode from "qrcode";
import { Button } from "./Button";
import styles from "./QrCodePanel.module.css";

interface QrCodePanelProps {
  /** URL completa que o QR deve codificar (deep link de volta pra esta
   * ficha/pavimento/obra). */
  url: string;
  titulo: string;
  code: string;
  /** Rótulo do TIPO de código (ex: "Código de Pavimento", "Código de Item —
   * Pilar") [2026-07-13] — decidido pelo chamador, que já sabe o contexto;
   * este painel é genérico (obra/pavimento/item) e não precisa conhecer a
   * taxonomia de tipo/kind pra exibir o rótulo certo. */
  rotuloTipo: string;
  /** Referência legível (ex: "Obra X › Térreo › Pilar P1") [2026-07-13] —
   * opcional, só texto de apoio ao lado do código pra humano entender de
   * cabeça, nunca o código de verdade. */
  referencia?: string;
}

/** QR code + botão imprimir [2026-07-12] — pedido do dono: usuário de
 * campo imprime o QR na ficha (item/pavimento/obra) pra facilitar acesso
 * de outros usuários depois, sem precisar digitar o código à mão.
 * Gerado 100% client-side (`qrcode`, lib pequena e sem dependências) — o
 * conteúdo do QR é só a URL pública, nunca dado sensível. */
export function QrCodePanel({ url, titulo, code, rotuloTipo, referencia }: QrCodePanelProps) {
  const [dataUrl, setDataUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    QRCode.toDataURL(url, { width: 240, margin: 2 })
      .then((gerado) => {
        if (!cancelado) setDataUrl(gerado);
      })
      .catch(() => {
        if (!cancelado) setDataUrl(null);
      });
    return () => {
      cancelado = true;
    };
  }, [url]);

  function imprimir() {
    window.print();
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.printArea} id="qr-print-area">
        {dataUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={dataUrl} alt={`QR code de acesso — ${titulo}`} className={styles.imagem} width={240} height={240} />
        ) : (
          <div className={styles.placeholder} aria-hidden="true" />
        )}
        <p className={styles.titulo}>{titulo}</p>
        <p className={styles.rotuloTipo}>{rotuloTipo}</p>
        <p className={styles.codigo}>{code}</p>
        {referencia && <p className={styles.referencia}>{referencia}</p>}
      </div>
      <Button variant="secondary" onClick={imprimir} className={styles.botaoImprimir}>
        <Printer size={18} aria-hidden="true" /> Imprimir QR
      </Button>
    </div>
  );
}
