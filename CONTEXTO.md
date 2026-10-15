# CONTEXTO.md · Memória viva do projeto

> **Leia este arquivo antes de qualquer tarefa.** Ele vence o SPEC e o PRD em caso de conflito. **Atualize ao final de cada etapa** (§1 e §5). O agente SQL também lê este arquivo inteiro.

## 1\. Estado do projeto

| etapa | status | observação |
| :---- | :---- | :---- |
| 1 · Scraping → bronze | ✅ concluída | 2 execuções de 2 páginas: 80 linhas, 40 UPCs distintos; payload cru conferido; SQL reaplicado com sucesso |
| 2 · Prata | ✅ concluída | view aplicada e reaplicada; 40 linhas e 40 UPCs distintos; sem preço, rating ou estoque nulo; sem categorias inválidas |
| 3 · Ouro | ✅ concluída | views aplicadas e reaplicadas; categorias somam 40 títulos, igual à prata; 3 faixas válidas; M1–M3 sem divergências |
| 4 · Agente SQL | ✅ concluída | 4 perguntas do PRD respondidas corretamente com OpenAI; SQLs gerados só consultaram prata/ouro; bloqueio de bronze validado |
| 5 · Interface Streamlit | ✅ concluída | 4 exemplos editáveis e opção com/sem contexto; agente recarregado a cada execução; pergunta real exibiu SQL em prata.livros, tabela com 40 livros e resposta; bronze bloqueada nos dois modos; servidor local reiniciado e HTTP 200 |
| 6 · Publicação no GitHub | ✅ concluída | branch `main` enviada a `renatosc3/Engenharia_de_dados`; código, SQL e README confirmados no GitHub; `.env` e segredos do Streamlit fora do Git |

&nbsp;

**Próximo passo:** aguardar validação da publicação e aprovação ou novo pedido\.

## 2\. Fonte de dados: books.toscrape.com

- Site público feito para treinar scraping. 50 páginas × 20 livros \= 1.000 livros.
- Listagem: `https://books.toscrape.com/catalogue/page-{n}.html` → links em `article.product_pod h3 a`.
- Detalhe do livro: título em `div.product_main h1`; preço em `div.product_main p.price_color`; avaliação na classe de `p.star-rating` (ex.: `star-rating Three`); tabela `table.table` com `UPC`, `Availability`, `Number of reviews`; categoria no 3º link de `ul.breadcrumb`.
- **Encoding:** o site não declara charset. Com `requests`, o `£` costuma chegar como `Â£`. Na bronze isso fica como veio; R2 resolve na prata.
- Campos do `payload` na bronze: `url`, `titulo`, `preco_raw`, `rating_raw`, `estoque_raw`, `upc`, `n_reviews_raw`, `categoria_raw`, `descricao`.

## 3\. Regras de negócio

**Bronze → prata**

- **R1 · Chave e duplicidade:** chave \= `upc`. Manter só a linha com o `_ingestao_em` mais recente.
- **R2 · Preço:** extrair só o número de `preco_raw` → `preco_gbp numeric(10,2)`. Moeda \= libra (GBP).
- **R3 · Avaliação:** `star-rating One..Five` → `rating` 1..5.
- **R4 · Estoque:** de `In stock (22 available)` extrair `22` → `estoque_qtd int`. Sem número \= 0\.
- **R5 · Reviews:** `n_reviews_raw` → `n_reviews int`.
- **R6 · Categoria:** `Default` e `Add a comment` não são categorias → `Sem categoria`.
- **R7 · Texto:** remover espaços nas pontas.

**Métricas (ouro)**

- **M1 · Valor em estoque** \= `preco_gbp × estoque_qtd`.
- **M2 · Bem avaliado** \= `rating >= 4`.
- **M3 · Faixa de preço:** `até £20` (\< 20\) · `£20–40` (20 a \< 40\) · `acima de £40` (≥ 40).
- **M4 · Moeda das respostas:** GBP. Se pedirem reais, usar o câmbio de §5. Rankings de categoria **excluem** `Sem categoria`, salvo pedido explícito.

## 4\. Dicionário de dados

**prata.livros** (1 linha \= 1 livro): `upc` · `titulo` · `categoria` · `preco_gbp` · `rating` · `estoque_qtd` · `n_reviews` · `url` · `_ingestao_em`

**ouro.livros:** prata \+ `valor_estoque_gbp` (M1) · `faixa_preco` (M3) · `bem_avaliado` (M2, bool)

**ouro.categorias** (1 linha \= 1 categoria): `categoria` · `qtd_titulos` · `preco_medio_gbp` · `rating_medio` · `estoque_unidades` · `valor_estoque_gbp` · `pct_bem_avaliados`

## 5\. Decisões

| data | decisão | motivo | quem |
| :---- | :---- | :---- | :---- |
| 08/10 | Bronze append-only; dedup só na prata | preservar o que veio de cada execução | Eng. Dados |
| 08/10 | Prata e ouro como views | base pequena, sempre atualizada | Eng. Dados |
| 08/10 | Câmbio fixo **£1 \= R\$ 7,20** | relatório da diretoria em reais (valor fictício da aula) | Financeiro |
| 08/10 | Agente SQL só lê `prata` e `ouro` | bronze tem lixo e duplicidade | Eng. Dados |
| 15/10 | `pct_bem_avaliados` usa escala de 0 a 100 | apresentar percentual por categoria de forma explícita | Eng. Dados |
| 15/10 | Interface local em Streamlit reutiliza o agente SQL da etapa 4 | mostrar pergunta, SQL executado, dados consultados e resposta sem duplicar regras de acesso | Eng. Dados |
| 15/10 | Alternância de contexto na interface mantém acesso somente a prata e ouro | permitir comparação do agente sem expor bronze pela interface | Eng. Dados |
| 15/10 | Publicar o código no repositório público `renatosc3/Engenharia_de_dados` | disponibilizar o projeto no GitHub solicitado, sem versionar credenciais | Eng. Dados |

&nbsp;

## 6\. Pendências

- Guardar histórico de preço (SCD2)? → fora do escopo de hoje.
