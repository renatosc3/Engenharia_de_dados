import argparse
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


def obter_conexao():
    load_dotenv(Path(__file__).with_name(".env"))
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL não configurada no .env")
    return psycopg.connect(url)


def executar_arquivo(caminho):
    sql = Path(caminho).read_text(encoding="utf-8")
    with obter_conexao() as conexao:
        conexao.execute(sql)
    print(f"SQL aplicado: {caminho}")


def executar_consulta(sql):
    with obter_conexao() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(sql)
            if cursor.description:
                print("\t".join(coluna.name for coluna in cursor.description))
                for linha in cursor:
                    print("\t".join(str(valor) for valor in linha))


def main():
    parser = argparse.ArgumentParser(description="Aplica um arquivo SQL ou executa uma consulta.")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("arquivo", nargs="?", help="Arquivo SQL a aplicar")
    grupo.add_argument("--query", help="Consulta SQL a imprimir")
    argumentos = parser.parse_args()
    if argumentos.query is not None:
        executar_consulta(argumentos.query)
    else:
        executar_arquivo(argumentos.arquivo)


if __name__ == "__main__":
    main()
