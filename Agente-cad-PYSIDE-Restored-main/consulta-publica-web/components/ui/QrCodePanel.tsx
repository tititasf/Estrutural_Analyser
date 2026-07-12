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
}

/** QR code + botão imprimir [2026-07-12] — pedido do dono: usuário de
 * campo imprime o QR na ficha (item/pavimento/obra) pra facilitar acesso
 * de outros usuários depois, sem precisar digitar o código à mão.
 * Gerado 100% client-side (`qrcode`, lib pequena e sem dependências) — o
 * conteúdo do QR é só a URL pública, nunca dado sensível. */
export function QrCodePanel({ url, titulo, code }: QrCodePanelProps) {
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
        <p className={styles.codigo}>{code}</p>
      </div>
      <Button variant="secondary" onClick={imprimir} className={styles.botaoImprimir}>
        <Printer size={18} aria-hidden="true" /> Imprimir QR
      </Button>
    </div>
  );
}
