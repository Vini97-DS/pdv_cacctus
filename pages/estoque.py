import streamlit as st
import pandas as pd
from sqlalchemy import text
import traceback

# --- 1. CONFIGURAÇÃO (DEVE SER A PRIMEIRA LINHA STREAMLIT) ---
st.set_page_config(page_title="Gestão de Estoque", layout="wide")

# --- SIDEBAR COM LOGO ---
st.sidebar.image("free_icon_1 (1).svg", width=100)
st.sidebar.divider()

# Conexão
conn = st.connection("postgresql", type="sql")

st.title("📦 Gestão de Estoque")

# --- 1. CADASTRO SIMPLIFICADO ---
st.subheader("➕ Cadastrar Novo Produto")
col1, col2 = st.columns(2)
nome = col1.text_input("Nome do Produto", key="nome_prod")
marca = col2.text_input("Marca (Ex: Ziggy, Heineken, etc.)") # Movido para coluna ao lado do nome
categoria = st.selectbox("Categoria", ["Essencia", "Carvão", "Bebidas", "Comidas", "Acessórios" ,"Outros"], key="cat_prod")

# Adicionada coluna para o Preço de Custo (Ação 1)
col3, col4, col5, col6 = st.columns(4)
preco_custo = col3.number_input("Preço de Custo (R$)", min_value=0.0, format="%.2f")
preco_venda = col4.number_input("Preço de Venda (R$)", min_value=0.0, format="%.2f")
estoque_inicial = col5.number_input("Qtd Inicial", min_value=0)
estoque_min = col6.number_input("Mínimo", min_value=1, value=5)

if st.button("Salvar Produto", type="primary"):
    if nome:
        try:
            with conn.session as s:
                s.execute(
                    text("""
                        INSERT INTO produtos (nome, marca, categoria, preco_custo, preco_venda, estoque_atual, estoque_minimo)
                        VALUES (:nome, :marca, :categoria, :custo, :preco, :estoque, :minimo)
                    """),
                    {
                        "nome": nome,
                        "categoria": categoria,
                        "marca": marca,
                        "custo": float(preco_custo), # Novo campo enviado ao banco
                        "preco": float(preco_venda),
                        "estoque": int(estoque_inicial),
                        "minimo": int(estoque_min)
                    }
                )
                s.commit()
            
            st.success(f"✅ '{nome}' salvo com sucesso!")
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
    with conn.session as s:
        # Query atualizada para mostrar marca e custo na tabela
        df = pd.read_sql(text("SELECT nome, marca, categoria, preco_custo, preco_venda, estoque_atual FROM produtos ORDER BY nome ASC"), s.bind)
    
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum produto cadastrado.")
except Exception as e:
    st.error(f"Erro ao carregar: {e}")