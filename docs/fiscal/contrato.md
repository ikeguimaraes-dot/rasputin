# Contrato fiscal do MVP

Este repositório implementa **conferência documental**, com suporte de contexto a Simples Nacional,
Lucro Presumido e Lucro Real. Não é um apurador universal de impostos. Nenhum enquadramento fiscal
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
| R02 | Indicação de ST em operação fora da ST | Regra aprovada por UF, regime, NCM, condições e vigência |
| R04 | Alíquota documental divergente | Exige consumidor final/operação explícitos e regra aprovada |
| R05 | CST/alíquotas de PIS/COFINS divergentes | Regra aprovada específica por regime e vigência |

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
posterior da página da fonte para reproduzir a decisão. A captura do conteúdo legal bruto e a
interpretação automática de alterações são trabalho da Fase 3.

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

## Fora desta entrega (fases posteriores)

SPED; R01/R03/R06/R07; coletores/cron legal; proposta de regra por IA; notificações;
consulta a APIs fiscais pagas; apuração mensal completa; certificação dos exemplos fiscais reais.
O caso sintético testa lógica, precedência e falsos positivos, sem atestar as hipóteses legais do
“caso de ouro” original, que ainda dependem de validação e arquivos reais anonimizados.
