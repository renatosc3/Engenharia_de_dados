# Livraria Inteligente

Pipeline de dados e agente SQL para responder perguntas sobre o catálogo do [Books to Scrape](https://books.toscrape.com/). Os dados ficam no PostgreSQL do Supabase, em camadas `bronze`, `prata` e `ouro`.

Repositório: [renatosc3/Engenharia_de_dados](https://github.com/renatosc3/Engenharia_de_dados).

## Executar a interface

Requer Python 3.11 ou superior.

```bash
python -m pip install -r requirements.txt
cp .env.exemplo .env
python -m streamlit run 05_interface_streamlit.py
```

Preencha no `.env` a conexão com o banco (`DATABASE_URL`), o provedor (`LLM_PROVIDER`), o modelo (`LLM_MODEL`) e a chave do provedor (`OPENAI_API_KEY` ou `ANTHROPIC_API_KEY`). O `.env` não deve ser enviado ao GitHub.

A interface permite escolher entre usar as regras do `CONTEXTO.md` ou somente o esquema do banco. Em ambos os modos, ela consulta apenas `prata` e `ouro`. As quatro perguntas do `PRD.md` aparecem como exemplos editáveis. Cada resposta mostra o SQL executado e os dados retornados em tabela.

## Estrutura

- `01_scraper_bronze.py`: coleta os livros e grava o payload cru em `bronze.livros`.
- `sql/01_prata.sql` e `sql/02_ouro.sql`: views de limpeza e métricas.
- `04_sql_agent.py`: gera, valida e executa consultas de leitura; também funciona pela linha de comando.
- `05_interface_streamlit.py`: interface local para perguntas e respostas.
- `aplicar_sql.py`: aplica arquivos SQL e executa consultas de verificação.

As regras de negócio e o estado do projeto estão em `CONTEXTO.md`. Os critérios de cada etapa estão em `SPEC.md`.
