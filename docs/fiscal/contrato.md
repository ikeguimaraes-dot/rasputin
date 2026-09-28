# Contrato fiscal — auditoria e apuração assistida

Este repositório implementa **conferência documental e apuração assistida**, com módulos para
Simples Nacional, Lucro Presumido e Lucro Real. Não é um apurador universal de impostos. Nenhum enquadramento fiscal
sintético dos testes está habilitado para produção.

## Regras implementadas

| Código | Implementação | Condição para uso |
|---|---|---|
| C01 | Divergências do mesmo código de produto | Severidade revisar; diferenças entre operações podem ser legítimas |
| C02 | Compatibilidade CFOP/CST/CSOSN | Regra aprovada por regime/contexto |
| C03 | CST 40/41 com valor; CST 00 com alíquota zero | Revisar; não conclui imposto devido |
| C04 | Valor vs. base × alíquota | Decimal, tolerância R$ 0,05; ausentes não viram zero |
| C05 | CEST zero e correspondência NCM/CEST | Zero é inconsistência; correspondência exige regra aprovada |
| C06 | NCM 00000000 / 99999999 | Inconsistência documental |
| C07 | IPI CST 50 em perfil não contribuinte | Revisar; não infere incidência a partir do CNAE |
| C08 | CFOP 5927/5949 | Revisar a natureza; não presume erro por descrição |
| C09 | Formação da base declarada de PIS/COFINS | Exige componentes da base e método declarado; admite outras exclusões |
| R01 | NCM na tabela oficial Siscomex | Respeita vigência do registro; ausência histórica inconclusiva não vira erro |
| R02 | Indicação de ST em operação fora da ST | Regra aprovada por UF, regime, NCM, condições e vigência |
| R04 | Alíquota documental divergente | Exige consumidor final/operação explícitos e regra aprovada |
| R05 | CST/alíquotas de PIS/COFINS divergentes | Regra específica aprovada; ou CST 01 e método de PIS/COFINS explicitamente declarado para alíquotas gerais oficiais |

C01, C03, C07, C08 e C09 não devem ser promovidas automaticamente a erro tributário confirmado.
Não há inferência de método PIS/COFINS pela maioria dos itens: quando não declarado, C09 registra
não avaliação. Campos IBS/CBS presentes no XML já são preservados, mas não avaliados.

## Base e aprovação

`fiscal_rules` é a base operacional do MVP, **isolada por escritório**. As tabelas tributárias
normalizadas previstas nas primeiras migrations continuam reservadas para evolução.
Cada regra informa: código, regimes, UF, prefixo NCM, condições, resultado esperado, vigência,
base legal, fonte e aprovação. Valores em percentual usam pontos percentuais (18 = 18%).
A aprovação publica uma definição imutável. Corrigir uma regra exige nova proposta/revisão.
Registros com a mesma precedência conflitante não são escolhidos arbitrariamente: a checagem é
registrada como não avaliada. Prefira vigências não sobrepostas; regras mais específicas podem
usar prioridade explícita. O motor ordena por prioridade, comprimento de prefixo e número de condições.

A planilha original `Tabela_Fiscal_AeB_Restaurantes_SP_27UF_2026-09.xlsx` não foi fornecida.
O importador preserva todas as linhas das abas `SP por NCM` e `27 Estados` com hash, aba e linha,
para revisão no admin. **Não interpreta automaticamente o layout desconhecido nem transforma
linhas incompletas em regras executáveis.** O responsável cria as propostas usando o formulário.
Linhas “Confirmar” e todas as demais permanecem sem efeito até aprovação explícita.

O hash do conjunto e as definições completas são preservados em `rule_sets`; não há dependência
posterior da página da fonte para reproduzir a decisão. O catálogo oficial acompanha fontes e hashes dos extratos efetivamente consultados. O tipo de captura
distingue extrato de texto integral; a tabela NCM original integral está arquivada. Não existe atualização
legal automática: alterar parâmetros exige nova versão, revisão de fontes e testes.

## Impacto e cobertura

- `potencial_documental` estima a diferença entre valor informado e esperado na mesma base.
- Não comprova recolhimento, crédito aproveitado ou direito à recuperação.
- R02 não estima impacto sem uma regra que sustente o cálculo.
- R04 nunca converte automaticamente o percentual mensal de restaurante em alíquota do item.
- PIS/COFINS monofásico, alíquota zero e CST precisam de enquadramento validado; prefixos genéricos
  não são uma lista fiscal oficial.
- Simples: não calcula DAS sem RBT12, anexo, faixa, segregação e demais dados necessários.
- Presumido/Real: não calcula IRPJ, CSLL, créditos ou saldo mensal com XMLs de saída apenas.
- Nenhuma base validada implica checagens fiscais “não avaliadas”, não conformidade comprovada.
- Sem protocolo XML a situação é desconhecida. Não há consulta online de autorização/cancelamento.
- Datas sem arquivos significam cobertura desconhecida, não “dia sem movimento”.

Fonte revisada para a distinção entre apuração mensal e destaque documental:
https://legislacao.fazenda.sp.gov.br/Paginas/dec51597.aspx

## Apuração assistida de 2026

O catálogo `worker/src/auditoria/data/parameters.json` contém parâmetros oficiais com referências
em `sources.json` e evidências em `docs/fiscal/fontes/`. Estes parâmetros não dependem da planilha
particular ausente. Não há dados sintéticos ativados como legislação.

| Módulo | Dados e condições necessários |
|---|---|
| Simples / Anexo I | Elegibilidade, RBT12 proporcionalizado quando cabível, receitas líquidas segregadas, situação do ICMS fora do DAS. A sexta faixa com ICMS ainda dentro do DAS é bloqueada: exige tratamento específico do sublimite. Outros anexos, exportação, isenções/reduções particulares e regime de caixa não são modelados. |
| Presumido trimestral | Comércio/alimentação a 8% IRPJ e 12% CSLL, serviços gerais a 32%, outras bases integrais e retenções. Majoração de 10% dos percentuais no excesso do limite; CSLL a partir do 2º trimestre/2026. Limites transportados são declarados. No 4º trimestre, parcela excedente e créditos de ajuste anual precisam ser previamente calculados na escrituração e informados; o sistema não recompõe sozinho os trimestres anteriores. |
| Real trimestral | Resultado contábil, adições, exclusões, prejuízos elegíveis e retenções. IRPJ/adicional e CSLL não financeira; compensação de até 30%. Sem incentivos ou hipóteses excepcionais. |
| Real anual | Balanço regular acumulado de janeiro até a competência, ano completo, prejuízos de anos anteriores, retenções acumuladas e antecipações efetivamente pagas. Suspensão/redução e ajuste de dezembro. Não calcula estimativa mensal sobre receita nem trata início/encerramento durante o ano. |
| PIS/COFINS mensal | Bases líquidas às alíquotas gerais, débitos especiais, créditos e retenções previamente enquadrados. Não aplica benefício nem crédito de compra automaticamente. |
| ICMS SP especial | Opção, condições do Decreto 51.597/2007, receita, exclusões e entradas com ST legalmente elegíveis. 4% mensal e dedução de 3,9%; jamais tratados como alíquota do item. |
| ICMS próprio normal | Débitos, créditos, estornos, ajustes e saldo anterior admitidos pela legislação da UF. Confronta valores escriturados; não determina alíquota estadual nem calcula ST, FCP ou DIFAL. |

Os campos necessários exigem valor explícito, inclusive zero; omissões produzem status incompleto.
O perfil precisa abranger todo o período. Os módulos não devem ser somados indiscriminadamente:
por exemplo, Real anual e trimestral são alternativas, assim como ICMS normal e especial.
Excedentes de deduções não significam automaticamente crédito restituível/compensável.
Não emite guias, não transmite declarações, não altera notas e não comprova recolhimento.

## Cobertura ainda não implementada

SPED; R03/R06/R07; incidência produto a produto nas 27 UFs; atualização legal automática;
classificação legal automática de monofásicos/bebidas/ST; apuração de IBS/CBS, ISS, IPI e folha;
notificações e APIs fiscais pagas. Campos IBS/CBS do XML continuam preservados sem apuração.
Os testes técnicos comprovam fórmulas e fluxos nas hipóteses documentadas; não constituem
certificação tributária integral de cada cliente.
