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
        desc = st.text_input("Descrição do Gasto")
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
                    st.success("Gasto registrado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

# --- TAB: COMPRA DE MERCADORIA (A inteligência que você pediu) ---
with tab_compra:
    st.subheader("Registrar Entrada de Estoque")
    try:
        with conn.session as s:
            # Pegamos os produtos e seus fatores de conversão
            df_prods = pd.read_sql(text("SELECT id, nome, fator_conversao FROM produtos ORDER BY nome"), s.bind)
        
        with st.form("form_compra_estoque", clear_on_submit=True):
            prod_sel = st.selectbox("Qual produto você comprou?", df_prods['nome'].tolist())
            
            c1, c2, c3 = st.columns([1, 1, 1])
            qtd_vol = c1.number_input("Qtd comprada", min_value=1, step=1)
            tipo_un = c2.selectbox("Formato", ["Unidades", "Caixas", "Pacotes"])
            total_pago = c3.number_input("Valor Total Pago (R$)", min_value=0.0, step=0.01)
            
            st.info("💡 O sistema calculará o custo unitário e atualizará o estoque automaticamente.")
            
            if st.form_submit_button("Confirmar Entrada de Mercadoria", type="primary", width='stretch'):
                if total_pago > 0:
                    # Recupera info do produto selecionado
                    p_info = df_prods[df_prods['nome'] == prod_sel].iloc[0]
                    
                    # Lógica de conversão: se for Caixa/Pacote, usa o fator. Se for unidade, fator é 1.
                    fator = p_info['fator_conversao'] if tipo_un != "Unidades" else 1
                    qtd_unidades_final = qtd_vol * fator
                    custo_unitario = total_pago / qtd_unidades_final
                    
                    try:
                        with conn.session as s:
                            # 1. Registra a saída no financeiro
                            s.execute(
                                text("INSERT INTO financeiro (descricao, valor, categoria, data_gasto) VALUES (:d, :v, 'Compra de Estoque', CURRENT_DATE)"),
                                {"d": f"Compra: {qtd_vol} {tipo_un} de {prod_sel}", "v": float(total_pago)}
                            )
                            # 2. Atualiza estoque e preço de custo no cadastro do produto
                            s.execute(
                                text("""
                                    UPDATE produtos 
                                    SET estoque_atual = estoque_atual + :q, 
                                        preco_custo = :pc 
                                    WHERE id = :id
                                """),
                                {"q": int(qtd_unidades_final), "pc": float(custo_unitario), "id": p_info['id']}
                            )
                            s.commit()
                        st.success(f"Sucesso! +{qtd_unidades_final} unidades no estoque. Custo: R$ {custo_unitario:.2f}/un")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao processar: {e}")
    except:
        st.info("Cadastre produtos no estoque primeiro.")

st.divider()

# --- 3. LISTAGEM RECENTE ---
st.subheader("📋 Últimos Lançamentos Financeiros")
try:
    with conn.session as s:
        df_list = pd.read_sql(text("SELECT data_gasto, descricao, categoria, valor FROM financeiro ORDER BY created_at DESC LIMIT 10"), s.bind)
    if not df_list.empty:
        st.dataframe(df_list, use_container_width=True, hide_index=True)
except:
    pass