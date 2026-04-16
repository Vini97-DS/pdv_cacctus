import streamlit as st
import pandas as pd
from sqlalchemy import text

# --- SIDEBAR COM LOGO ---
st.sidebar.image("free_icon_1 (1).svg", width=100)
st.sidebar.divider()


st.set_page_config(page_title="Ponto de Venda", layout="wide")
conn = st.connection("postgresql", type="sql")

st.title("🛒 Ponto de Venda")

# --- 1. CARREGAR DADOS ---
try:
    with conn.session as s:
        produtos_df = pd.read_sql(
            text("SELECT id, nome, preco_venda, estoque_atual FROM produtos WHERE estoque_atual > 0 ORDER BY nome ASC"),
            s.bind
        )
except Exception as e:
    st.error(f"Erro ao carregar produtos: {e}")
    produtos_df = pd.DataFrame()

TAXAS = {"Dinheiro": 0.0, "Pix": 0.0, "Débito": 0.019, "Crédito": 0.045}

if produtos_df.empty:
    st.warning("Sem produtos disponíveis em estoque para venda.")
else:
    # --- 2. FORMULÁRIO DE VENDA ---
    with st.form("form_venda", clear_on_submit=True):
        col1, col2 = st.columns(2)
        produto_nome = col1.selectbox("Selecione o Produto", produtos_df['nome'].tolist())
        metodo_pagto = col2.selectbox("Forma de Pagamento", list(TAXAS.keys()))

        col3, col4 = st.columns(2)
        quantidade = col3.number_input("Quantidade", min_value=1, step=1)
        
        prod_row = produtos_df[produtos_df['nome'] == produto_nome].iloc[0]
        total_bruto = float(prod_row['preco_venda']) * quantidade
        taxa_valor = total_bruto * TAXAS[metodo_pagto]
        total_liq = total_bruto - taxa_valor

        st.info(f"💰 **Total Bruto: R$ {total_bruto:.2f}** | Taxa: R$ {taxa_valor:.2f} | **Líquido: R$ {total_liq:.2f}**")

        if st.form_submit_button("Confirmar Venda", width='stretch'):
            if quantidade > int(prod_row['estoque_atual']):
                st.error(f"Estoque insuficiente! Disponível: {int(prod_row['estoque_atual'])}")
            else:
                try:
                    with conn.session as s:
                        # PASSO A: Inserir na tabela 'vendas' e capturar o ID gerado
                        result = s.execute(
                            text("""
                                INSERT INTO vendas (valor_bruto, metodo_pagamento, taxa_maquininha, valor_liquido)
                                VALUES (:bruto, :metodo, :taxa, :liquido)
                                RETURNING id
                            """),
                            {
                                "bruto": total_bruto,
                                "metodo": metodo_pagto,
                                "taxa": taxa_valor,
                                "liquido": total_liq
                            }
                        )
                        # Captura o UUID da venda recém-criada
                        venda_id = result.fetchone()[0]

                        # PASSO B: Inserir na tabela 'itens_venda' usando o venda_id
                        s.execute(
                            text("""
                                INSERT INTO itens_venda (venda_id, produto_id, quantidade, preco_unitario)
                                VALUES (:v_id, :p_id, :q, :preco)
                            """),
                            {
                                "v_id": venda_id,
                                "p_id": prod_row['id'],
                                "q": quantidade,
                                "preco": float(prod_row['preco_venda'])
                            }
                        )

                        # PASSO C: Atualizar estoque do produto
                        s.execute(
                            text("UPDATE produtos SET estoque_atual = estoque_atual - :q WHERE id = :id"),
                            {"q": quantidade, "id": prod_row['id']}
                        )
                        
                        s.commit()
                    
                    st.success(f"Venda de {quantidade}x {produto_nome} realizada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar venda: {e}")

# --- 3. HISTÓRICO RECENTE ---
st.divider()
st.subheader("📋 Últimas 5 Vendas")
try:
    with conn.session as s:
        historico = pd.read_sql(
            text("SELECT data_venda, valor_bruto, metodo_pagamento, valor_liquido FROM vendas ORDER BY data_venda DESC LIMIT 5"),
            s.bind
        )
    if not historico.empty:
        st.dataframe(historico, width='stretch')
except Exception as e:
    st.error(f"Erro ao carregar histórico: {e}")