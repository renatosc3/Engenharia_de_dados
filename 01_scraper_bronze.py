import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin
from uuid import uuid4

import requests
from bs4 import BeautifulSoup
from psycopg.types.json import Jsonb

from aplicar_sql import obter_conexao


BASE = "https://books.toscrape.com/catalogue/"
CABECALHOS = {"User-Agent": "LivrariaDados/1.0 (estudo de catalogo)"}


def baixar_pagina(url):
    resposta = requests.get(url, headers=CABECALHOS, timeout=30)
    resposta.raise_for_status()
    return BeautifulSoup(resposta.text, "html.parser")


def listar_livros(numero_pagina):
    url = urljoin(BASE, f"page-{numero_pagina}.html")
    pagina = baixar_pagina(url)
    links = pagina.select("article.product_pod h3 a")
    if len(links) != 20:
        raise ValueError(f"Página {numero_pagina}: esperados 20 livros, encontrados {len(links)}")
    return [urljoin(url, link["href"]) for link in links]


def ler_tabela(pagina):
    return {
        linha.select_one("th").get_text(): linha.select_one("td").get_text()
        for linha in pagina.select("table.table tr")
    }


def raspar_livro(url):
    pagina = baixar_pagina(url)
    tabela = ler_tabela(pagina)
    categoria = pagina.select("ul.breadcrumb a")[2].get_text()
    secao_descricao = pagina.select_one("#product_description")
    descricao = secao_descricao.find_next_sibling("p").get_text() if secao_descricao else ""
    payload = {
        "url": url,
        "titulo": pagina.select_one("div.product_main h1").get_text(),
        "preco_raw": pagina.select_one("div.product_main p.price_color").get_text(),
        "rating_raw": " ".join(pagina.select_one("p.star-rating")["class"]),
        "estoque_raw": tabela["Availability"],
        "upc": tabela["UPC"],
        "n_reviews_raw": tabela["Number of reviews"],
        "categoria_raw": categoria,
        "descricao": descricao,
    }
    return url, payload


def gravar_livros(livros, execucao_id):
    sql = Path(__file__).with_name("sql").joinpath("00_bronze.sql").read_text(encoding="utf-8")
    with obter_conexao() as conexao:
        conexao.execute(sql)
        with conexao.cursor() as cursor:
            cursor.executemany(
                "insert into bronze.livros (fonte_url, payload, _execucao_id) values (%s, %s, %s)",
                [(url, Jsonb(payload), execucao_id) for url, payload in livros],
            )


def main():
    parser = argparse.ArgumentParser(description="Raspa livros e grava os dados crus na bronze.")
    parser.add_argument("--paginas", type=int, required=True, choices=range(1, 51), metavar="N")
    argumentos = parser.parse_args()
    urls = []
    for numero in range(1, argumentos.paginas + 1):
        urls.extend(listar_livros(numero))
    with ThreadPoolExecutor(max_workers=8) as executor:
        livros = list(executor.map(raspar_livro, urls))
    execucao_id = str(uuid4())
    gravar_livros(livros, execucao_id)
    print(f"Execução {execucao_id}: {len(livros)} livros gravados em bronze.livros")


if __name__ == "__main__":
    main()
