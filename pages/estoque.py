import streamlit as st
import pandas as pd
from sqlalchemy import text
import traceback

st.write(f"Conectando com o usuário: {st.secrets['connections']['postgresql']['username']}")
st.set_page_config(page_title="Gestão de Estoque", layout="wide")
conn = st.connection("postgresql", type="sql")

st.title("📦 Gestão de Estoque")

# --- 1. CADASTRO SIMPLIFICADO ---
st.subheader("➕ Cadastrar Novo Produto")
col1, col2 = st.columns(2)
nome = col1.text_input("Nome do Produto", key="nome_prod")
categoria = col2.selectbox("Categoria", ["Essencia", "Carvão", "Bebidas", "Comidas", "Acessórios" ,"Outros"], key="cat_prod")

col3, col4, col5 = st.columns(3)
preco = col3.number_input("Preço de Venda (R$)", min_value=0.0, format="%.2f")
estoque_inicial = col4.number_input("Qtd Inicial", min_value=0)
estoque_min = col5.number_input("Mínimo", min_value=1, value=5)

if st.button("Salvar Produto", type="primary"):
    if nome:
        try:
            print(f">>> Tentando salvar: {nome}")
            
            # A correção: Usar a sessão (s) para executar o comando
            with conn.session as s:
                s.execute(
                    text("""
                        INSERT INTO produtos (nome, categoria, preco_venda, estoque_atual, estoque_minimo)
                        VALUES (:nome, :categoria, :preco, :estoque, :minimo)
                    """),
                    {
                        "nome": nome,
                        "categoria": categoria,
                        "preco": float(preco),
                        "estoque": int(estoque_inicial),
                        "minimo": int(estoque_min)
                    }
                )
                s.commit() # Importante para gravar no banco
            
            st.success(f"✅ '{nome}' salvo com sucesso!")
            print(">>> Sucesso no banco!")
            st.rerun()
            
        except Exception as e:
            st.error(f"Erro no banco: {e}")
            print(f"!!! ERRO NO BANCO: {traceback.format_exc()}")
    else:
        st.warning("O nome é obrigatório.")

st.divider()

# --- 2. LISTAGEM ---
st.subheader("📋 Produtos em Inventário")
try:
    # Busca direta via sessão para evitar o "Running" infinito
    with conn.session as s:
        df = pd.read_sql(text("SELECT nome, categoria, preco_venda, estoque_atual FROM produtos ORDER BY nome ASC"), s.bind)
    
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum produto cadastrado.")
except Exception as e:
    st.error(f"Erro ao carregar: {e}")