import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import date

st.set_page_config(page_title="Financeiro VIP", layout="wide")
conn = st.connection("postgresql", type="sql")

# --- SIDEBAR COM LOGO ---
st.sidebar.image("free_icon_1 (1).svg", width=100)
st.sidebar.divider()

st.title("💰 Gestão Financeira")

# --- 1. DASHBOARD DE FLUXO DE CAIXA ---
try:
    with conn.session as s:
        # Busca Entradas (Vendas de hoje)
        vendas_hoje = s.execute(text("SELECT SUM(valor_bruto) FROM vendas WHERE data_venda::date = CURRENT_DATE")).fetchone()[0] or 0
        # Busca Saídas (Financeiro de hoje)
        gastos_hoje = s.execute(text("SELECT SUM(valor) FROM financeiro WHERE data_gasto = CURRENT_DATE")).fetchone()[0] or 0
        
    saldo = float(vendas_hoje) - float(gastos_hoje)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Vendas Hoje", f"R$ {vendas_hoje:,.2f}")
    m2.metric("Saídas Hoje", f"R$ {gastos_hoje:,.2f}")
    m3.metric("Saldo do Dia", f"R$ {saldo:,.2f}", delta=f"{saldo:,.2f}")
except:
    st.error("Erro ao carregar resumo financeiro.")

st.divider()

# --- 2. LANÇAMENTOS ---
tab_saida, tab_compra = st.tabs(["💸 Saída Simples (Gasto)", "🛒 Compra de Mercadoria (Estoque)"])

# --- TAB: SAÍDA SIMPLIFICADA (Luz, Aluguel, etc) ---
with tab_saida:
    with st.form("form_saida", clear_on_submit=True):
        st.subheader("Registrar Gasto Geral")
        desc = st.text_input("Descrição do Gasto (Ex: Aluguel, Energia)")
        val = st.number_input("Valor (R$)", min_value=0.0, step=0.01)
        cat = st.selectbox("Categoria", ["Infraestrutura", "Pessoal", "Marketing", "Outros"])
        
        if st.form_submit_button("Lançar Gasto", type="primary"):
            if desc and val > 0:
                try:
                    with conn.session as s:
                        s.execute(
                            text("INSERT INTO financeiro (descricao, valor, categoria, data_gasto) VALUES (:d, :v, :c, CURRENT_DATE)"),
                            {"d": desc, "v": float(val), "c": cat}
                        )
                        s.commit()
                    st.success("Gasto registrado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar gasto: {e}")

# --- TAB: COMPRA DE MERCADORIA (ENTRADA DIRETA) ---
with tab_compra:
    st.subheader("Registrar Entrada de Mercadoria")
    try:
        with conn.session as s:
            df_prods = pd.read_sql(text("SELECT id, nome FROM produtos ORDER BY nome"), s.bind)
        
        opcoes_prods = ["+ CADASTRAR NOVO PRODUTO"] + df_prods['nome'].tolist()
        escolha = st.selectbox("Selecione o Produto ou Cadastre um Novo", opcoes_prods)

        with st.form("form_compra_estoque", clear_on_submit=True):
            if escolha == "+ CADASTRAR NOVO PRODUTO":
                st.info("✨ Cadastro de novo item")
                nome_novo = st.text_input("Nome do Produto")
                marca_novo = st.text_input("Marca")
                cat_novo = st.selectbox("Categoria", ["Essencia", "Carvão", "Bebidas", "Comidas", "Acessórios", "Outros"])
                p_venda_sugerido = st.number_input("Preço de Venda Final (R$)", min_value=0.0, step=0.1)
            else:
                st.write(f"📦 Lançando entrada para: **{escolha}**")
            
            st.divider()
            c1, c2 = st.columns(2)
            qtd_total = c1.number_input("Quantidade Total de Unidades (Ex: 60, 10, 500)", min_value=1, step=1)
            total_pago = c2.number_input("Valor Total Pago na Compra (R$)", min_value=0.0, step=0.01)
            
            st.caption("Obs: O custo unitário será calculado dividindo o valor total pela quantidade.")

            if st.form_submit_button("Confirmar Compra e Atualizar Estoque", type="primary", width='stretch'):
                try:
                    with conn.session as s:
                        # 1. Lógica para Produto Novo
                        if escolha == "+ CADASTRAR NOVO PRODUTO":
                            if not nome_novo:
                                st.error("O nome do produto é obrigatório!")
                                st.stop()
                            
                            res = s.execute(
                                text("""
                                    INSERT INTO produtos (nome, marca, categoria, preco_venda, estoque_atual, estoque_minimo)
                                    VALUES (:n, :m, :cat, :pv, 0, 5) RETURNING id
                                """),
                                {"n": nome_novo, "m": marca_novo, "cat": cat_novo, "pv": float(p_venda_sugerido)}
                            )
                            p_id = res.fetchone()[0]
                            p_nome_final = nome_novo
                        else:
                            p_id = df_prods[df_prods['nome'] == escolha].iloc[0]['id']
                            p_nome_final = escolha

                        # 2. Cálculo de Custo Unitário Direto
                        custo_unitario = total_pago / qtd_total if qtd_total > 0 else 0

                        # 3. Registrar no Financeiro
                        s.execute(
                            text("INSERT INTO financeiro (descricao, valor, categoria, data_gasto) VALUES (:d, :v, 'Compra de Estoque', CURRENT_DATE)"),
                            {"d": f"Compra: {qtd_total} un de {p_nome_final}", "v": float(total_pago)}
                        )

                        # 4. Atualizar Estoque e Preço de Custo
                        s.execute(
                            text("UPDATE produtos SET estoque_atual = estoque_atual + :q, preco_custo = :pc WHERE id = :id"),
                            {"q": int(qtd_total), "pc": float(custo_unitario), "id": p_id}
                        )
                        s.commit()
                    
                    st.success(f"✅ Sucesso! {qtd_total} unidades de '{p_nome_final}' adicionadas ao estoque.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro no processamento: {e}")
    except Exception as e:
        st.info("Carregando banco de dados...")

st.divider()

# --- 3. HISTÓRICO RECENTE ---
st.subheader("📋 Últimos Lançamentos")
try:
    with conn.session as s:
        df_list = pd.read_sql(text("""
            SELECT data_gasto as Data, descricao as Descrição, categoria as Categoria, valor as Valor 
            FROM financeiro ORDER BY created_at DESC LIMIT 10
        """), s.bind)
    if not df_list.empty:
        st.dataframe(df_list, use_container_width=True, hide_index=True)
except:
    pass