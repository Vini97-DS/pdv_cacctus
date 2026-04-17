import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import date

st.set_page_config(page_title="Financeiro", layout="wide")
conn = st.connection("postgresql", type="sql")

# --- SIDEBAR COM LOGO ---
st.sidebar.image("free_icon_1 (1).svg", width=100)
st.sidebar.divider()

st.title("💰 Gestão Financeira")

# --- 1. RESUMO DO DIA (DASHBOARD RÁPIDO) ---
st.subheader(f"Fluxo de Caixa - {date.today().strftime('%d/%m/%Y')}")

try:
    with conn.session as s:
        # Busca Entradas (Vendas de hoje)
        vendas_hoje = s.execute(text("SELECT SUM(valor_bruto) FROM vendas WHERE data_venda::date = CURRENT_DATE")).fetchone()[0] or 0
        
        # Busca Saídas (Gastos de hoje)
        gastos_hoje = s.execute(text("SELECT SUM(valor) FROM financeiro WHERE data_gasto = CURRENT_DATE")).fetchone()[0] or 0
        
    saldo = vendas_hoje - gastos_hoje
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Entradas (Vendas)", f"R$ {vendas_hoje:,.2f}")
    m2.metric("Saídas (Custos)", f"R$ {gastos_hoje:,.2f}", delta_color="normal")
    m3.metric("Saldo do Dia", f"R$ {saldo:,.2f}", delta=f"{saldo:,.2f}")

except Exception as e:
    st.error(f"Erro ao carregar resumo: {e}")

st.divider()

# --- 2. LANÇAR NOVA SAÍDA ---
col_form, col_list = st.columns([1, 2])

with col_form:
    st.subheader("➕ Registrar Gasto")
    with st.form("form_financeiro", clear_on_submit=True):
        desc = st.text_input("Descrição (Ex: Aluguel, Compra Carvão)")
        valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01)
        cat = st.selectbox("Categoria", ["Insumos", "Infraestrutura", "Pessoal", "Marketing", "Outros"])
        data = st.date_input("Data do Gasto", value=date.today())
        
        if st.form_submit_button("Lançar Saída", type="primary", width='stretch'):
            if desc and valor > 0:
                try:
                    with conn.session as s:
                        s.execute(
                            text("INSERT INTO financeiro (descricao, valor, categoria, data_gasto) VALUES (:d, :v, :c, :dt)"),
                            {"d": desc, "v": float(valor), "c": cat, "dt": data}
                        )
                        s.commit()
                    st.success("Saída registrada!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

with col_list:
    st.subheader("📋 Últimos Lançamentos")
    try:
        with conn.session as s:
            df_gastos = pd.read_sql(text("SELECT descricao, valor, categoria, data_gasto FROM financeiro ORDER BY data_gasto DESC LIMIT 10"), s.bind)
        if not df_gastos.empty:
            st.dataframe(df_gastos, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum gasto registrado recentemente.")
    except:
        pass