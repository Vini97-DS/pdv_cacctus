import streamlit as st
from sqlalchemy import text

st.set_page_config(page_title="Clientes", layout="wide")
conn = st.connection("postgresql", type="sql")

st.title("👤 Cadastro de Clientes")

with st.form("novo_cliente", clear_on_submit=True):
    col1, col2 = st.columns(2)
    nome = col1.text_input("Nome Completo")
    telefone = col2.text_input("WhatsApp (com DDD)")
    
    if st.form_submit_button("Cadastrar Cliente", width='stretch'):
        if nome and telefone:
            try:
                with conn.session as s:
                    s.execute(
                        text("INSERT INTO clientes (nome, telefone) VALUES (:n, :t)"),
                        {"n": nome, "t": telefone}
                    )
                    s.commit()
                st.success(f"Cliente {nome} cadastrado!")
            except Exception as e:
                st.error(f"Erro: {e}")
        else:
            st.warning("Preencha nome e telefone.")