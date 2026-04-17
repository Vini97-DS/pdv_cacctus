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
        # Puxamos o essencial para o operacional
        df = pd.read_sql(text("""
            SELECT id, nome, marca, categoria, estoque_atual, estoque_minimo, preco_venda, fator_conversao 
            FROM produtos ORDER BY nome ASC
        """), s.bind)
    
    if not df.empty:
        # Destacamos o que está acabando
        estoque_baixo = df[df['estoque_atual'] <= df['estoque_minimo']]
        if not estoque_baixo.empty:
            st.warning(f"⚠️ **Atenção:** {len(estoque_baixo)} itens estão com estoque baixo ou zerado!")

        # Tabela formatada
        st.dataframe(
            df[['nome', 'marca', 'categoria', 'estoque_atual', 'preco_venda', 'fator_conversao']], 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("Nenhum produto cadastrado. Vá ao Financeiro para realizar a primeira compra.")
except Exception as e:
    st.error(f"Erro ao carregar inventário: {e}")

st.divider()

# --- 2. ÁREA DE AJUSTE RÁPIDO ---
with st.expander("🛠️ Ajustar Preços ou Fator de Conversão"):
    if not df.empty:
        prod_edit = st.selectbox("Selecione o produto para editar", df['nome'].tolist())
        detalhes = df[df['nome'] == prod_edit].iloc[0]
        
        col1, col2, col3 = st.columns(3)
        novo_preco = col1.number_input("Novo Preço de Venda (R$)", value=float(detalhes['preco_venda']), step=0.5)
        novo_fator = col2.number_input("Fator de Conversão (Qtd por Caixa)", value=int(detalhes['fator_conversao']), min_value=1)
        novo_minimo = col3.number_input("Estoque Mínimo", value=int(detalhes['estoque_minimo']), min_value=0)
        
        if st.button("Salvar Alterações", type="primary"):
            try:
                with conn.session as s:
                    s.execute(text("""
                        UPDATE produtos 
                        SET preco_venda = :pv, fator_conversao = :fc, estoque_minimo = :em 
                        WHERE id = :id
                    """), {"pv": novo_preco, "fc": novo_fator, "em": novo_minimo, "id": detalhes['id']})
                    s.commit()
                st.success("Produto atualizado!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")