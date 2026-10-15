import argparse
import json
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

from aplicar_sql import obter_conexao


PASTA = Path(__file__).parent
BLOCO_SQL = re.compile(r"```sql\s*(.*?)```", re.IGNORECASE | re.DOTALL)
TABELA_REFERENCIADA = re.compile(r"\b(?:from|join)\s+([a-z_][\w.]*)", re.IGNORECASE)
CTE = re.compile(r"\b(?:with|,)\s*([a-z_]\w*)\s+as\s*\(", re.IGNORECASE)


def obter_schema(sem_contexto, somente_prata_ouro=False):
    filtro = "and c.table_schema in ('prata', 'ouro')" if not sem_contexto or somente_prata_ouro else ""
    consulta = f"""
        select c.table_schema, c.table_name, c.column_name, c.data_type
        from information_schema.columns c
        join information_schema.tables t
          on t.table_schema = c.table_schema and t.table_name = c.table_name
        where c.table_schema not in ('information_schema', 'pg_catalog')
          and c.table_schema not like 'pg_%'
          {filtro}
        order by c.table_schema, c.table_name, c.ordinal_position
    """
    with obter_conexao() as conexao:
        linhas = conexao.execute(consulta).fetchall()
    tabelas = {}
    for schema, tabela, coluna, tipo in linhas:
        tabelas.setdefault(f"{schema}.{tabela}", []).append(f"{coluna} {tipo}")
    return "\n".join(f"{tabela}: {', '.join(colunas)}" for tabela, colunas in tabelas.items())


def montar_system_prompt(sem_contexto, responder=False, somente_prata_ouro=False):
    schema = obter_schema(sem_contexto, somente_prata_ouro)
    if sem_contexto:
        instrucoes = "Responda em português usando somente o resultado SQL recebido." if responder else (
            "Você responde perguntas sobre o banco PostgreSQL. Gere uma única consulta "
            "SELECT ou WITH em um bloco ```sql. Se a pergunta for ambígua, peça esclarecimento."
        )
        if somente_prata_ouro and not responder:
            instrucoes += " Consulte somente views dos schemas prata e ouro."
        return f"{instrucoes}\n\nSchema real:\n{schema}"
    contexto = PASTA.joinpath("CONTEXTO.md").read_text(encoding="utf-8")
    instrucoes = (
        "Você é o agente SQL da livraria. Responda em português usando somente o resultado "
        "da consulta recebida e as regras do CONTEXTO.md. Apresente valores monetários "
        "com duas casas decimais; não gere SQL."
        if responder else
        "Você é o agente SQL da livraria. Responda em português usando somente prata e ouro. "
        "Gere uma única consulta SELECT ou WITH por pergunta, dentro de um bloco ```sql. "
        "Use as regras e decisões do CONTEXTO.md, inclusive câmbio e exclusão de 'Sem categoria' "
        "em rankings quando aplicáveis. Se a pergunta for ambígua, peça esclarecimento sem SQL. "
        "Não consulte bronze nem tabelas fora de prata e ouro."
    )
    return f"{instrucoes}\n\nCONTEXTO.md completo:\n{contexto}\n\nSchema real:\n{schema}"


def ler_resposta_openai(dados):
    textos = [
        parte["text"]
        for item in dados.get("output", [])
        if item.get("type") == "message"
        for parte in item.get("content", [])
        if parte.get("type") == "output_text"
    ]
    return "\n".join(textos).strip()


def chamar_openai(modelo, chave, sistema, pedido):
    resposta = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {chave}"},
        json={"model": modelo, "instructions": sistema, "input": pedido, "store": False},
        timeout=120,
    )
    verificar_resposta_http(resposta, "OpenAI")
    return ler_resposta_openai(resposta.json())


def chamar_anthropic(modelo, chave, sistema, pedido):
    resposta = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": chave, "anthropic-version": "2023-06-01"},
        json={
            "model": modelo,
            "max_tokens": 2048,
            "system": sistema,
            "messages": [{"role": "user", "content": pedido}],
        },
        timeout=120,
    )
    verificar_resposta_http(resposta, "Anthropic")
    return "\n".join(
        bloco["text"] for bloco in resposta.json().get("content", []) if bloco.get("type") == "text"
    ).strip()


def verificar_resposta_http(resposta, provedor):
    if resposta.ok:
        return
    try:
        mensagem = resposta.json().get("error", {}).get("message", "requisição recusada")
    except ValueError:
        mensagem = "requisição recusada"
    raise RuntimeError(f"{provedor} HTTP {resposta.status_code}: {mensagem}")


def consultar_llm(sistema, pedido):
    provedor = os.getenv("LLM_PROVIDER", "").lower()
    modelo = os.getenv("LLM_MODEL", "")
    if provedor not in ("openai", "anthropic") or not modelo:
        raise ValueError("Configure LLM_PROVIDER (openai|anthropic) e LLM_MODEL no .env")
    chave = os.getenv("OPENAI_API_KEY" if provedor == "openai" else "ANTHROPIC_API_KEY")
    if not chave:
        raise ValueError(f"Configure a chave de API do provedor {provedor} no .env")
    texto = (
        chamar_openai(modelo, chave, sistema, pedido)
        if provedor == "openai"
        else chamar_anthropic(modelo, chave, sistema, pedido)
    )
    if not texto:
        raise RuntimeError("O LLM devolveu uma resposta vazia")
    return texto


def remover_literais(sql):
    partes = []
    dentro = False
    indice = 0
    while indice < len(sql):
        caractere = sql[indice]
        if caractere == "'":
            if dentro and indice + 1 < len(sql) and sql[indice + 1] == "'":
                partes.extend("  ")
                indice += 2
                continue
            dentro = not dentro
            partes.append(" ")
        else:
            partes.append(" " if dentro else caractere)
        indice += 1
    if dentro:
        raise ValueError("SQL contém texto entre aspas não fechado")
    return "".join(partes)


def extrair_sql(texto):
    blocos = BLOCO_SQL.findall(texto)
    if len(blocos) != 1:
        raise ValueError("O LLM deve gerar exatamente um bloco ```sql")
    return blocos[0].strip()


def validar_sql(sql, sem_contexto, somente_prata_ouro=False):
    visivel = remover_literais(sql)
    if not re.match(r"\s*(select|with)\b", visivel, re.IGNORECASE):
        raise ValueError("Somente SELECT ou WITH são permitidos")
    if re.search(r'"|\$|--|/\*|\*/', visivel):
        raise ValueError("Aspas em identificadores, comentários e dollar quoting não são permitidos")
    if visivel.count(";") > 1 or (";" in visivel and not visivel.rstrip().endswith(";")):
        raise ValueError("Gere apenas uma consulta SQL")
    if re.search(r"\b(insert|update|delete|drop|alter|create|copy|grant|revoke|truncate|call|do|execute|set)\b", visivel, re.IGNORECASE):
        raise ValueError("A consulta contém um comando não permitido")
    if not sem_contexto or somente_prata_ouro:
        if re.search(r"\bpg_[a-z_]\w*\s*\(", visivel, re.IGNORECASE):
            raise ValueError("Funções internas do PostgreSQL não são permitidas")
        if re.search(r"\bbronze\b", visivel, re.IGNORECASE):
            raise ValueError("Consultas à bronze são proibidas no modo com contexto")
        ctes = {nome.lower() for nome in CTE.findall(visivel)}
        tabelas = TABELA_REFERENCIADA.findall(visivel)
        if not tabelas:
            raise ValueError("A consulta deve ler prata ou ouro")
        for nome in tabelas:
            if nome.lower() not in ctes and not re.fullmatch(r"(?:prata|ouro)\.[a-z_]\w*", nome, re.IGNORECASE):
                raise ValueError(f"Tabela fora de prata/ouro: {nome}")
    return sql.rstrip().removesuffix(";").rstrip()


def executar_sql(sql):
    consulta = f"select * from ({sql}) as resultado limit 50"
    with obter_conexao() as conexao:
        conexao.execute("set transaction read only")
        conexao.execute("set local statement_timeout = '10s'")
        conexao.execute("set local search_path = prata, ouro")
        with conexao.cursor() as cursor:
            cursor.execute(consulta)
            colunas = [coluna.name for coluna in cursor.description]
            return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]


def processar_pergunta(pergunta, sem_contexto=False, somente_prata_ouro=False):
    load_dotenv(PASTA / ".env")
    sistema = montar_system_prompt(sem_contexto, somente_prata_ouro=somente_prata_ouro)
    pedido = f"Pergunta: {pergunta}\nGere uma consulta SQL para respondê-la."
    erros = []
    for tentativa in range(1, 4):
        texto = consultar_llm(sistema, pedido)
        if not BLOCO_SQL.search(texto) and "```" not in texto:
            if texto.rstrip().endswith("?"):
                return {"esclarecimento": texto, "erros": erros}
            erro = "A resposta não contém um bloco ```sql"
            erros.append(f"Tentativa {tentativa}: {erro}")
            pedido = f"Pergunta original: {pergunta}\nSua tentativa anterior:\n{texto}\n{erro}. Gere a consulta."
            continue
        try:
            sql = validar_sql(extrair_sql(texto), sem_contexto, somente_prata_ouro)
            linhas = executar_sql(sql)
        except Exception as erro:
            erros.append(f"Tentativa {tentativa}: {erro}")
            pedido = (
                f"Pergunta original: {pergunta}\nSua tentativa anterior:\n{texto}\n"
                f"Erro ao validar ou executar: {erro}\nCorrija e devolva um único bloco ```sql."
            )
            continue
        resultado = json.dumps(linhas, ensure_ascii=False, default=str)
        resposta = consultar_llm(
            montar_system_prompt(sem_contexto, responder=True, somente_prata_ouro=somente_prata_ouro),
            f"Pergunta original: {pergunta}\nSQL executado: {sql}\nResultado: {resultado}\n"
            "Responda à pergunta em português, usando somente o resultado acima. Não gere SQL.",
        )
        return {
            "sql": sql,
            "linhas": json.loads(resultado),
            "resposta": resposta,
            "tentativa": tentativa,
            "erros": erros,
        }
    raise RuntimeError("Não foi possível executar uma consulta válida em três tentativas. " + " | ".join(erros))


def responder_pergunta(pergunta, sem_contexto):
    resultado = processar_pergunta(pergunta, sem_contexto)
    for erro in resultado["erros"]:
        print(f"Erro na {erro.lower()}")
    if "esclarecimento" in resultado:
        print(f"Resposta: {resultado['esclarecimento']}")
        return
    print(f"SQL gerado (tentativa {resultado['tentativa']}):\n{resultado['sql']}")
    print(f"Resultado: {json.dumps(resultado['linhas'], ensure_ascii=False)}")
    print(f"Resposta: {resultado['resposta']}")


def main():
    load_dotenv(PASTA / ".env")
    parser = argparse.ArgumentParser(description="Agente SQL para perguntas sobre a livraria.")
    parser.add_argument("--sem-contexto", action="store_true")
    parser.add_argument("--pergunta", action="append", help="Pergunta para execução não interativa; pode repetir.")
    argumentos = parser.parse_args()
    if argumentos.pergunta:
        for pergunta in argumentos.pergunta:
            responder_pergunta(pergunta, argumentos.sem_contexto)
        return
    while True:
        try:
            pergunta = input("Pergunta (vazio para sair): ").strip()
        except EOFError:
            break
        if not pergunta:
            break
        responder_pergunta(pergunta, argumentos.sem_contexto)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, requests.RequestException) as erro:
        raise SystemExit(f"Erro: {erro}") from None
