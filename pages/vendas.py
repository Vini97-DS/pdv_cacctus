import streamlit as st
import pandas as pd
from sqlalchemy import text

st.set_page_config(page_title="Vendas de Balcão", layout="wide")
conn = st.connection("postgresql", type="sql")

# --- SIDEBAR COM LOGO ---
st.sidebar.image("free_icon_1 (1).svg", width=100)
st.sidebar.divider()

st.title("🛒 Venda de Balcão / Carrinho")

# --- 1. INICIALIZAÇÃO DO CARRINHO (MEMÓRIA) ---
if 'carrinho' not in st.session_state:
    st.session_state.carrinho = []

# --- 2. SELEÇÃO DE PRODUTOS ---
try:
    with conn.session as s:
        prods_df = pd.read_sql(text("SELECT id, nome, preco_venda, estoque_atual FROM produtos WHERE estoque_atual > 0 ORDER BY nome"), s.bind)
        # Busca clientes para o seletor
        clientes_df = pd.read_sql(text("SELECT id, nome FROM clientes ORDER BY nome"), s.bind)

    col_prod, col_qtd, col_add = st.columns([3, 1, 1])

    with col_prod:
        p_selecionado = st.selectbox("Escolha o Produto", prods_df['nome'].tolist())
    with col_qtd:
        qtd_venda = st.number_input("Qtd", min_value=1, value=1)
    with col_add:
        st.write(" ") # Alinhamento
        if st.button("Adicionar", use_container_width=True):
            detalhes = prods_df[prods_df['nome'] == p_selecionado].iloc[0]
            # Adiciona ao carrinho na memória
            st.session_state.carrinho.append({
                "id": detalhes['id'],
                "nome": detalhes['nome'],
                "qtd": qtd_venda,
                "preco": float(detalhes['preco_venda']),
                "subtotal": float(detalhes['preco_venda'] * qtd_venda)
            })
            st.toast(f"{p_selecionado} adicionado!")

except Exception as e:
    st.error(f"Erro ao carregar produtos: {e}")

st.divider()

# --- 3. EXIBIÇÃO DO CARRINHO ---
if st.session_state.carrinho:
    col_lista, col_resumo = st.columns([2, 1])

    with col_lista:
        st.subheader("Itens no Carrinho")
        df_carrinho = pd.DataFrame(st.session_state.carrinho)
        
        # Botão para limpar carrinho
        if st.button("Esvaziar Carrinho"):
            st.session_state.carrinho = []
            st.rerun()

        # Exibe os itens de forma limpa
        for idx, item in enumerate(st.session_state.carrinho):
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"**{item['nome']}**")
            c2.write(f"{item['qtd']}x R$ {item['preco']:.2f}")
            if c3.button("Remover", key=f"rem_{idx}"):
                st.session_state.carrinho.pop(idx)
                st.rerun()

    with col_resumo:
        st.subheader("Finalização")
        # Conversão explícita para float nativo do Python para evitar erro de np.float64
        total_venda = float(df_carrinho['subtotal'].sum())
        st.write(f"### Total: R$ {total_venda:.2f}")
        
        # --- CAMPOS EXTRAS (VIP) ---
        cliente_opcoes = ["Nenhum"] + clientes_df['nome'].tolist()
        cliente_sel = st.selectbox("Vincular Cliente (Opcional)", cliente_opcoes)
        
        id_cliente_final = None
        if cliente_sel != "Nenhum":
            id_cliente_final = int(clientes_df[clientes_df['nome'] == cliente_sel].iloc[0]['id'])

        canal = st.radio("Canal de Venda", ["Balcão", "Delivery"], horizontal=True)
        metodo = st.selectbox("Forma de Pagamento", ["Dinheiro", "Pix", "Débito", "Crédito"])
        
        if st.button("Confirmar e Finalizar", type="primary", use_container_width=True):
            try:
                # Lógica de taxas com conversão para float nativo
                taxas_map = {"Dinheiro": 0.0, "Pix": 0.0, "Débito": 0.019, "Crédito": 0.045}
                v_taxa = float(total_venda * taxas_map[metodo])
                v_liq = float(total_venda - v_taxa)

                with conn.session as s:
                    # 1. Criar a Venda (incluindo canal_venda e cliente_id)
                    res = s.execute(
                        text("""
                            INSERT INTO vendas (valor_bruto, metodo_pagamento, taxa_maquininha, valor_liquido, canal_venda, cliente_id)
                            VALUES (:bruto, :metodo, :taxa, :liquido, :canal, :c_id)
                            RETURNING id
                        """),
                        {
                            "bruto": total_venda, 
                            "metodo": metodo, 
                            "taxa": v_taxa, 
                            "liquido": v_liq, 
                            "canal": canal,
                            "c_id": id_cliente_final
                        }
                    )
                    venda_id = res.fetchone()[0]

                    # 2. Inserir itens e baixar estoque
                    for item in st.session_state.carrinho:
                        s.execute(
                            text("INSERT INTO itens_venda (venda_id, produto_id, quantidade, preco_unitario) VALUES (:v, :p, :q, :pr)"),
                            {"v": venda_id, "p": int(item['id']), "q": int(item['qtd']), "pr": float(item['preco'])}
                        )
                        s.execute(
                            text("UPDATE produtos SET estoque_atual = estoque_atual - :q WHERE id = :p"),
                            {"q": int(item['qtd']), "p": int(item['id'])}
                        )
                    
                    s.commit()
                
                st.success("Venda realizada com sucesso!")
                st.session_state.carrinho = [] # Limpa o carrinho
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao finalizar: {e}")

else:
    st.info("O carrinho está vazio. Adicione produtos acima.")