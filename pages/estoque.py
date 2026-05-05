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
        df = pd.read_sql(text("""
            SELECT id, nome, marca, categoria, estoque_atual, estoque_minimo, preco_venda, preco_custo
            FROM produtos ORDER BY nome ASC
        """), s.bind)
    
    if not df.empty:
        # Indicadores de Estoque Baixo
        estoque_baixo = df[df['estoque_atual'] <= df['estoque_minimo']]
        if not estoque_baixo.empty:
            st.error(f"🚨 **Atenção:** {len(estoque_baixo)} itens abaixo do nível mínimo!")

        # Tabela formatada para o usuário
        st.dataframe(
            df[['nome', 'marca', 'categoria', 'estoque_atual', 'preco_venda', 'preco_custo']], 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "nome": "Produto",
                "marca": "Marca",
                "categoria": "Categoria",
                "estoque_atual": "Qtd em Estoque",
                "preco_venda": st.column_config.NumberColumn("Preço de Venda", format="R$ %.2f"),
                "preco_custo": st.column_config.NumberColumn("Preço de Custo", format="R$ %.2f"),
            }
        )
    else:
        st.info("Nenhum produto cadastrado. Realize uma compra na aba Financeiro.")
except Exception as e:
    st.error(f"Erro ao carregar inventário: {e}")

st.divider()

# --- 2. ÁREA DE EDIÇÃO COMPLETA ---
with st.expander("✏️ Editar Produto"):
    if not df.empty:
        prod_edit = st.selectbox("Selecione o produto", df['nome'].tolist(), key="edit_select")
        detalhes = df[df['nome'] == prod_edit].iloc[0]
        
        col1, col2 = st.columns(2)
        novo_nome     = col1.text_input("Nome do Produto", value=str(detalhes['nome']))
        nova_marca    = col2.text_input("Marca", value=str(detalhes['marca']))

        col3, col4 = st.columns(2)
        nova_qtd      = col3.number_input("Quantidade em Estoque", value=int(detalhes['estoque_atual']), min_value=0)
        novo_minimo   = col4.number_input("Alerta de Estoque Mínimo", value=int(detalhes['estoque_minimo']), min_value=0)

        col5, col6 = st.columns(2)
        novo_preco    = col5.number_input("Preço de Venda (R$)", value=float(detalhes['preco_venda']), step=0.5, min_value=0.0)
        novo_custo    = col6.number_input("Preço de Custo (R$)", value=float(detalhes['preco_custo']) if detalhes['preco_custo'] is not None else 0.0, step=0.5, min_value=0.0)
        
        if st.button("💾 Salvar Alterações", type="primary", use_container_width=True):
            try:
                with conn.session as s:
                    s.execute(text("""
                        UPDATE produtos 
                        SET nome = :nome, marca = :marca, estoque_atual = :ea,
                            preco_venda = :pv, preco_custo = :pc, estoque_minimo = :em
                        WHERE id = :id::uuid
                    """), {
                        "nome": novo_nome, "marca": nova_marca, "ea": nova_qtd,
                        "pv": novo_preco, "pc": novo_custo, "em": novo_minimo,
                        "id": str(detalhes['id'])
                    })
                    s.commit()
                st.success(f"Produto '{novo_nome}' atualizado com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

st.divider()

# --- 3. ÁREA DE EXCLUSÃO DE PRODUTO ---
with st.expander("🗑️ Excluir Produto"):
    if not df.empty:
        prod_del = st.selectbox("Selecione o produto a excluir", df['nome'].tolist(), key="del_select")
        detalhes_del = df[df['nome'] == prod_del].iloc[0]

        st.warning(f"Você está prestes a excluir **{prod_del}** permanentemente. Essa ação não pode ser desfeita.")

        confirmar = st.checkbox("Confirmo que desejo excluir este produto")

        if st.button("🗑️ Excluir Produto", type="primary", disabled=not confirmar, use_container_width=True):
            try:
                with conn.session as s:
                    s.execute(text("DELETE FROM produtos WHERE id = :id::uuid"), {"id": str(detalhes_del['id'])})
                    s.commit()
                st.success(f"Produto '{prod_del}' excluído com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao excluir: {e}")