import importlib

import streamlit as st


agente_sql = importlib.reload(importlib.import_module("04_sql_agent"))
EXEMPLOS = [
    "Qual categoria tem o maior valor em estoque, em reais?",
    "Quantos livros bem avaliados custam menos de £20?",
    "Quantos livros únicos temos na base?",
    "Qual o preço médio por faixa de preço?",
]


def mostrar_resultado(resultado):
    if "esclarecimento" in resultado:
        st.info(resultado["esclarecimento"])
        return

    st.subheader("Resposta")
    st.write(resultado["resposta"])
    st.subheader("SQL gerado")
    st.code(resultado["sql"], language="sql")
    st.subheader("Dados retornados pelo banco")
    if resultado["linhas"]:
        st.dataframe(resultado["linhas"], hide_index=True)
    else:
        st.info("A consulta não retornou linhas.")


def main():
    st.set_page_config(page_title="Livraria Inteligente")
    st.title("Livraria Inteligente")
    st.write("Faça uma pergunta sobre os livros, categorias, preços ou estoque.")
    modo = st.radio("Contexto do agente", ["Com contexto", "Sem contexto"], horizontal=True)
    st.caption(
        "Com contexto aplica as regras do projeto. Sem contexto usa apenas o esquema do banco. "
        "A interface consulta somente prata e ouro nos dois modos."
    )
    exemplo = st.selectbox("Exemplos de perguntas", ["Escrever minha pergunta", *EXEMPLOS])

    with st.form("pergunta"):
        pergunta = st.text_input(
            "Sua pergunta",
            value="" if exemplo == "Escrever minha pergunta" else exemplo,
            key=f"pergunta_{exemplo}",
        )
        enviar = st.form_submit_button("Perguntar")

    if not enviar:
        return
    if not pergunta.strip():
        st.warning("Digite uma pergunta antes de enviar.")
        return

    try:
        with st.spinner("Consultando o banco..."):
            resultado = agente_sql.processar_pergunta(
                pergunta.strip(),
                sem_contexto=modo == "Sem contexto",
                somente_prata_ouro=True,
            )
    except Exception as erro:
        st.error(f"Não foi possível responder: {erro}")
        return

    mostrar_resultado(resultado)


if __name__ == "__main__":
    main()
