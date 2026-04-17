import streamlit as st
import pandas as pd
from sqlalchemy import text

st.set_page_config(page_title="Gestão de Comandas", layout="wide")
conn = st.connection("postgresql", type="sql")

# --- SIDEBAR COM LOGO ---
st.sidebar.image("free_icon_1 (1).svg", width=100)
st.sidebar.divider()

st.title("📑 Gestão de Comandas")

tab1, tab2 = st.tabs(["Abrir Nova", "Comandas Ativas"])

# --- TAB 1: ABRIR NOVA COMANDA ---
with tab1:
    try:
        with conn.session as s:
            clientes_df = pd.read_sql(text("SELECT id, nome FROM clientes ORDER BY nome"), s.bind)
        
        with st.form("abrir_comanda", clear_on_submit=True):
            st.subheader("Vincular Cliente")
            cliente_opcoes = ["Nenhum (Venda Avulsa)"] + clientes_df['nome'].tolist()
            cliente_sel = st.selectbox("Selecione o Cliente", cliente_opcoes)
            
            # Campo extra só aparece se não selecionar cliente, para casos de mesa/identificador avulso
            titulo_avulso = ""
            if cliente_sel == "Nenhum (Venda Avulsa)":
                titulo_avulso = st.text_input("Identificador Manual (Ex: Mesa 01, Balcão)")

            if st.form_submit_button("Abrir Comanda", width='stretch', type="primary"):
                id_cliente = None
                nome_comanda = ""

                if cliente_sel != "Nenhum (Venda Avulsa)":
                    id_cliente = clientes_df[clientes_df['nome'] == cliente_sel].iloc[0]['id']
                    nome_comanda = cliente_sel
                else:
                    nome_comanda = titulo_avulso

                if nome_comanda:
                    try:
                        with conn.session as s:
                            s.execute(
                                text("INSERT INTO comandas (numero_comanda, status, cliente_id) VALUES (:num, 'Aberta', :c_id)"),
                                {"num": nome_comanda, "c_id": id_cliente}
                            )
                            s.commit()
                        st.success(f"Comanda para '{nome_comanda}' aberta!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao abrir comanda: {e}")
                else:
                    st.warning("Por favor, selecione um cliente ou digite um identificador.")
    except Exception as e:
        st.error(f"Erro ao carregar lista de clientes: {e}")

# --- TAB 2: GERENCIAR COMANDAS ATIVAS ---
with tab2:
    try:
        with conn.session as s:
            prods_df = pd.read_sql(text("SELECT id, nome, preco_venda FROM produtos WHERE estoque_atual > 0 ORDER BY nome"), s.bind)
            comandas_df = pd.read_sql(text("""
                SELECT c.id, c.numero_comanda, cl.nome as nome_cliente, c.cliente_id 
                FROM comandas c 
                LEFT JOIN clientes cl ON c.cliente_id = cl.id
                WHERE c.status = 'Aberta' ORDER BY c.created_at DESC
            """), s.bind)

        if comandas_df.empty:
            st.info("Nenhuma comanda aberta.")
        else:
            for _, comanda in comandas_df.iterrows():
                # O título agora é o nome do cliente ou o identificador digitado
                label_comanda = f"👤 {comanda['numero_comanda']}"
                
                with st.expander(label_comanda):
                    # --- LANÇAMENTO DE ITENS ---
                    st.write("**Lançar Consumo**")
                    c1, c2, c3 = st.columns([3, 1, 1])
                    p_nome = c1.selectbox("Produto", prods_df['nome'].tolist(), key=f"p_{comanda['id']}")
                    qtd = c2.number_input("Qtd", min_value=1, value=1, key=f"q_{comanda['id']}")
                    
                    if c3.button("Lançar", key=f"add_{comanda['id']}", width='stretch'):
                        p_sel = prods_df[prods_df['nome'] == p_nome].iloc[0]
                        try:
                            with conn.session as s:
                                s.execute(
                                    text("INSERT INTO itens_comanda (comanda_id, produto_id, quantidade, preco_unitario) VALUES (:c_id, :p_id, :q, :preco)"),
                                    {"c_id": comanda['id'], "p_id": p_sel['id'], "q": qtd, "preco": float(p_sel['preco_venda'])}
                                )
                                s.commit()
                            st.toast("Item adicionado!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao lançar item: {e}")

                    # --- LISTAGEM ---
                    st.divider()
                    with conn.session as s:
                        itens_consumidos = pd.read_sql(
                            text("""
                                SELECT i.id as item_id, p.nome, i.quantidade, i.preco_unitario, (i.quantidade * i.preco_unitario) as subtotal
                                FROM itens_comanda i
                                JOIN produtos p ON i.produto_id = p.id
                                WHERE i.comanda_id = :cid
                            """), s.bind, params={"cid": comanda['id']}
                        )
                    
                    if not itens_consumidos.empty:
                        for _, row in itens_consumidos.iterrows():
                            col_item, col_excluir = st.columns([4, 1])
                            col_item.write(f"{row['quantidade']}x {row['nome']} - R$ {row['subtotal']:.2f}")
                            with col_excluir.popover("🗑️"):
                                if st.button("Confirmar Exclusão", key=f"del_{row['item_id']}", type="primary"):
                                    with conn.session as s:
                                        s.execute(text("DELETE FROM itens_comanda WHERE id = :id"), {"id": row['item_id']})
                                        s.commit()
                                    st.rerun()

                        total_conta = float(itens_consumidos['subtotal'].sum())
                        st.subheader(f"Total: R$ {total_conta:.2f}")
                        
                        # --- FECHAMENTO ---
                        with st.popover(f"Finalizar e Cobrar R$ {total_conta:.2f}", width='stretch'):
                            num_pess = st.number_input("Dividir por", min_value=1, value=1, key=f"div_{comanda['id']}")
                            if num_pess > 1:
                                st.info(f"R$ {total_conta/num_pess:.2f} por pessoa")
                            
                            st.divider()
                            metodo = st.selectbox("Forma de Pagamento", ["Dinheiro", "Pix", "Débito", "Crédito"], key=f"met_{comanda['id']}")
                            
                            if st.button("Confirmar Pagamento", key=f"conf_{comanda['id']}", type="primary", width='stretch'):
                                try:
                                    taxas_map = {"Dinheiro": 0.0, "Pix": 0.0, "Débito": 0.019, "Crédito": 0.045}
                                    v_taxa = float(total_conta * taxas_map[metodo])
                                    v_liq = float(total_conta - v_taxa)

                                    with conn.session as s:
                                        s.execute(
                                            text("""
                                                INSERT INTO vendas (valor_bruto, metodo_pagamento, taxa_maquininha, valor_liquido, canal_venda, cliente_id)
                                                VALUES (:bruto, :metodo, :taxa, :liquido, 'Lounge', :c_id)
                                            """),
                                            {"bruto": total_conta, "metodo": metodo, "taxa": v_taxa, "liquido": v_liq, "c_id": comanda['cliente_id']}
                                        )
                                        s.execute(text("UPDATE produtos SET estoque_atual = estoque_atual - ic.quantidade FROM itens_comanda ic WHERE produtos.id = ic.produto_id AND ic.comanda_id = :c"), {"c": comanda['id']})
                                        s.execute(text("UPDATE comandas SET status = 'Fechada' WHERE id = :c"), {"c": comanda['id']})
                                        s.commit()
                                    st.success("Venda Lounge registrada!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao finalizar: {e}")
                    else:
                        st.write("Comanda vazia.")
    except Exception as e:
        st.error(f"Erro ao processar comandas: {e}")