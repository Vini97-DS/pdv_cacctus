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
    with st.form("abrir_comanda", clear_on_submit=True):
        numero = st.text_input("Número ou Identificador (Ex: Mesa 01)")
        if st.form_submit_button("Abrir Comanda", width='stretch'):
            if numero:
                try:
                    with conn.session as s:
                        s.execute(
                            text("INSERT INTO comandas (numero_comanda, status) VALUES (:num, 'Aberta')"),
                            {"num": numero}
                        )
                        s.commit()
                    st.success(f"Comanda '{numero}' aberta!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

# --- TAB 2: GERENCIAR COMANDAS ATIVAS ---
with tab2:
    try:
        with conn.session as s:
            # Busca produtos para o seletor
            prods_df = pd.read_sql(text("SELECT id, nome, preco_venda FROM produtos WHERE estoque_atual > 0 ORDER BY nome"), s.bind)
            # Busca comandas que estão com status 'Aberta'
            comandas_df = pd.read_sql(text("SELECT id, numero_comanda FROM comandas WHERE status = 'Aberta' ORDER BY created_at DESC"), s.bind)

        if comandas_df.empty:
            st.info("Nenhuma comanda aberta.")
        else:
            for _, comanda in comandas_df.iterrows():
                with st.expander(f"📌 {comanda['numero_comanda']}"):
                    
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
                                    text("""
                                        INSERT INTO itens_comanda (comanda_id, produto_id, quantidade, preco_unitario)
                                        VALUES (:c_id, :p_id, :q, :preco)
                                    """),
                                    {"c_id": comanda['id'], "p_id": p_sel['id'], "q": qtd, "preco": float(p_sel['preco_venda'])}
                                )
                                s.commit()
                            st.toast("Item adicionado!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao lançar: {e}")

                    # --- LISTAGEM DO CONSUMO ATUAL ---
                    st.divider()
                    with conn.session as s:
                        # Query agora traz o ID da linha para podermos excluir especificamente
                        itens_consumidos = pd.read_sql(
                            text("""
                                SELECT i.id as item_id, i.produto_id, p.nome, i.quantidade, i.preco_unitario, (i.quantidade * i.preco_unitario) as subtotal
                                FROM itens_comanda i
                                JOIN produtos p ON i.produto_id = p.id
                                WHERE i.comanda_id = :cid
                            """),
                            s.bind, params={"cid": comanda['id']}
                        )
                    
                    if not itens_consumidos.empty:
                        # Exibição visual com botão de excluir por linha
                        for _, row in itens_consumidos.iterrows():
                            col_item, col_excluir = st.columns([4, 1])
                            col_item.write(f"{row['quantidade']}x {row['nome']} - R$ {row['subtotal']:.2f}")
                            
                            # Confirmação de exclusão Sim/Não
                            with col_excluir.popover("🗑️", help="Excluir este item"):
                                st.warning("Deseja excluir?")
                                if st.button("Sim, excluir", key=f"del_{row['item_id']}", type="primary"):
                                    try:
                                        with conn.session as s:
                                            s.execute(text("DELETE FROM itens_comanda WHERE id = :id"), {"id": row['item_id']})
                                            s.commit()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro: {e}")

                        total_conta = itens_consumidos['subtotal'].sum()
                        st.subheader(f"Total: R$ {total_conta:.2f}")
                        
                        # --- BOTÃO DE FECHAMENTO (POPOVER) ---
                        with st.popover(f"Finalizar e Cobrar R$ {total_conta:.2f}", width='stretch'):
                            metodo_pagto = st.selectbox("Forma de Pagamento", ["Dinheiro", "Pix", "Débito", "Crédito"], key=f"met_{comanda['id']}")
                            
                            if st.button("Confirmar Pagamento", key=f"conf_{comanda['id']}", type="primary", width='stretch'):
                                try:
                                    valor_bruto_puro = float(total_conta)
                                    taxas_map = {"Dinheiro": 0.0, "Pix": 0.0, "Débito": 0.019, "Crédito": 0.045}
                                    v_taxa = float(valor_bruto_puro * taxas_map[metodo_pagto])
                                    v_liq = float(valor_bruto_puro - v_taxa)

                                    with conn.session as s:
                                        res = s.execute(
                                            text("""
                                                INSERT INTO vendas (valor_bruto, metodo_pagamento, taxa_maquininha, valor_liquido)
                                                VALUES (:bruto, :metodo, :taxa, :liquido)
                                                RETURNING id
                                            """),
                                            {"bruto": valor_bruto_puro, "metodo": metodo_pagto, "taxa": v_taxa, "liquido": v_liq}
                                        )
                                        nova_venda_id = res.fetchone()[0]

                                        s.execute(
                                            text("""
                                                INSERT INTO itens_venda (venda_id, produto_id, quantidade, preco_unitario)
                                                SELECT :v_id, produto_id, quantidade, preco_unitario 
                                                FROM itens_comanda WHERE comanda_id = :c_id
                                            """),
                                            {"v_id": nova_venda_id, "c_id": comanda['id']}
                                        )

                                        s.execute(
                                            text("""
                                                UPDATE produtos 
                                                SET estoque_atual = estoque_atual - ic.quantidade
                                                FROM itens_comanda ic
                                                WHERE produtos.id = ic.produto_id AND ic.comanda_id = :c_id
                                            """),
                                            {"c_id": comanda['id']}
                                        )

                                        s.execute(
                                            text("UPDATE comandas SET status = 'Fechada' WHERE id = :c_id"),
                                            {"c_id": comanda['id']}
                                        )
                                        
                                        s.commit()
                                    
                                    st.success("Venda registrada e estoque atualizado!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao fechar: {e}")
                    else:
                        st.write("Comanda vazia.")

    except Exception as e:
        st.error(f"Erro ao processar comandas: {e}")