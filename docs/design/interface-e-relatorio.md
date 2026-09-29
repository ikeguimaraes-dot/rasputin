# Interface e relatório ao cliente

A interface mantém verde profundo (#193b32 / #1a493b), papel (#f5f6f1) e lima
(#d8f078). O painel mostra o cliente atual, etapas clicáveis e a última conferência.
Os indicadores se referem aos dados reais da análise, nunca a uma conformidade
tributária inferida. A navegação, os formulários e a leitura foram revisados para
celular e desktop. Animações respeitam `prefers-reduced-motion`.

O relatório PDF tem resumo executivo, gráfico da composição da base, exemplos,
localização de cada diferença, instrução de revisão e identificação preservada.
A exportação baixa o relatório privado salvo. A ação de reemissão atualiza a
apresentação usando os resultados imutáveis. Não reavalia
regras, não altera documentos e não envia mensagens automaticamente. O botão
“Copiar mensagem para o cliente” apenas copia um texto de acompanhamento.

## Mascote

Asset criado pela ferramenta integrada `image_gen`, usando a imagem fornecida
pelo usuário como referência de edição. O original do usuário foi preservado.
Arquivos finais idênticos (PNG com transparência):

- `apps/web/public/brand/rasputin-mascot.png` — interface.
- `worker/src/auditoria/assets/rasputin-mascot.png` — PDF, incorporado como data URL.

Prompt utilizado:

> Edit the provided mascot screenshot into a clean production brand asset for the
> Rasputin restaurant tax review web application. Preserve the exact lovable green
> furry creature identity: two long asymmetric eyestalks, large turquoise blue eyes,
> green and yellow soft fur, squat broad feet, friendly curious expression. Show the
> full creature centered with generous clear space around it, no cropping;
> reconstruct the obscured right side naturally. Remove ALL social media UI
> overlays, heart, comment icon, digits, borders and screenshot background. High
> quality clean softly lit 3D character render, faithful to reference, no clothes,
> no props, no words. Truly transparent background with alpha, isolated mascot PNG;
> subtle ground shadow only. Portrait composition, usable as a website hero mascot.
> Save the generated asset for this project.

## Verificação

`apps/web/scripts/test-review-browser.mjs` verifica painel, resumo, gráfico,
mascote, filtro, exportação, modal por teclado e ausência de alertas especulativos
com dados sintéticos. Os PDFs devem ser renderizados com Poppler e revisados
visualmente; a extração de texto isolada não verifica diagramação.
