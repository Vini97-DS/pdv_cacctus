import streamlit as st
import pandas as pd
from sqlalchemy import text

st.set_page_config(page_title="Gestão de Estoque", layout="wide")
conn = st.connection("postgresql", type="sql")

# --- SIDEBAR COM LOGO ---
st.sidebar.image("free_icon_1 (1).svg", width=100)
st.sidebar.divider()

st.title("📦 Inventário e Preços")

# --- 1. TABELA DE PRODUTOS ---
try:
    with conn.session as s:
        # Puxamos apenas o necessário para a visualização operacional
        df = pd.read_sql(text("""
            SELECT id, nome, marca, categoria, estoque_atual, estoque_minimo, preco_venda 
            FROM produtos ORDER BY nome ASC
        """), s.bind)
    
    if not df.empty:
        # Indicadores de Estoque Baixo
        estoque_baixo = df[df['estoque_atual'] <= df['estoque_minimo']]
        if not estoque_baixo.empty:
            st.error(f"🚨 **Atenção:** {len(estoque_baixo)} itens abaixo do nível mínimo!")

        # Tabela formatada para o usuário
        st.dataframe(
            df[['nome', 'marca', 'categoria', 'estoque_atual', 'preco_venda']], 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "nome": "Produto",
                "marca": "Marca",
                "categoria": "Categoria",
                "estoque_atual": "Qtd em Estoque",
                "preco_venda": st.column_config.NumberColumn("Preço de Venda", format="R$ %.2f")
            }
        )
    else:
        st.info("Nenhum produto cadastrado. Realize uma compra na aba Financeiro.")
except Exception as e:
    st.error(f"Erro ao carregar inventário: {e}")

st.divider()

# --- 2. ÁREA DE AJUSTE RÁPIDO ---
with st.expander("🛠️ Ajustar Preço de Venda ou Estoque Mínimo"):
    if not df.empty:
        prod_edit = st.selectbox("Selecione o produto", df['nome'].tolist())
        detalhes = df[df['nome'] == prod_edit].iloc[0]
        
        col1, col2 = st.columns(2)
        novo_preco = col1.number_input("Novo Preço de Venda (R$)", value=float(detalhes['preco_venda']), step=0.5)
        novo_minimo = col2.number_input("Alerta de Estoque Mínimo", value=int(detalhes['estoque_minimo']), min_value=0)
        
        if st.button("Atualizar Produto", type="primary", use_container_width=True):
            try:
                with conn.session as s:
                    s.execute(text("""
                        UPDATE produtos 
                        SET preco_venda = :pv, estoque_minimo = :em 
                        WHERE id = :id
                    """), {"pv": novo_preco, "em": novo_minimo, "id": detalhes['id']})
                    s.commit()
                st.success(f"Alterações em '{prod_edit}' salvas!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")