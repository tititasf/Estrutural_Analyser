const fs = require('fs');
let c = fs.readFileSync('app/ficha/[code]/page.tsx', 'utf8');

c = c.replace('const semLateral = aba === "materiais" && !qrAberto;', 
  'const semLateral = aba === "materiais" && !qrAberto;\n\n  const classificacao = ficha.campos["Classificação"] || ficha.campos["Classificacao"] || "";\n  const nivel = ficha.campos["Nível Relativo"] || ficha.campos["Nível"] || ficha.campos["Laje B #1 — Nível"] || Object.entries(ficha.campos).find(e => e[0].toLowerCase().includes("nível") || e[0].toLowerCase().includes("nivel"))?.[1] || "";'
);

c = c.replace('onVoltar={handleVoltar}', 'onVoltar={handleVoltar}\n        classificacao={classificacao}\n        nivel={nivel}');

c = c.replace(/\{\/\* Coluna Direita: Cabeçalho, Metadados e Ações \*\/\}[\s\S]*?<\/aside>\s*\}\)/, 
  '{qrAberto && origemAtual && (\n            <div style={{ marginTop: "20px" }}>\n              <QrCodePanel\n                url={${origemAtual}/ficha/}\n                titulo={tituloFicha(ficha)}\n                code={ficha.code}\n                rotuloTipo={rotuloCodigoItem(ficha.tipo)}\n                referencia={[ficha.obra_rotulo, ficha.pavimento_label, tituloFicha(ficha)].filter(Boolean).join(" • ")}\n              />\n            </div>\n          )}'
);

fs.writeFileSync('app/ficha/[code]/page.tsx', c, 'utf8');