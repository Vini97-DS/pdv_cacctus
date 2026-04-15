import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text

st.set_page_config(page_title="Tabacaria BI", layout="wide")
conn = st.connection("postgresql", type="sql")

st.title("📊 Painel de Controle — Tabacaria")

# --- ALERTAS DE ESTOQUE ---
st.subheader("🔔 Alertas de Inventário")
try:
    with conn.session as s:
        df_alertas = pd.read_sql(
            text("SELECT nome, estoque_atual, estoque_minimo FROM produtos WHERE estoque_atual <= estoque_minimo"),
            s.bind
        )

    if not df_alertas.empty:
        with st.expander(f"⚠️ {len(df_alertas)} ITENS COM ESTOQUE CRÍTICO", expanded=True):
            st.warning(f"{len(df_alertas)} produtos precisam de reposição!")
            st.table(df_alertas.rename(columns={
                "nome": "Produto", "estoque_atual": "Qtd Atual", "estoque_minimo": "Mínimo"
            }))
    else:
        st.success("✅ Todos os produtos estão em níveis normais.")
except Exception as e:
    st.error(f"Erro ao verificar estoque: {e}")

st.divider()

# --- RESUMO FINANCEIRO ---
st.subheader("💰 Resumo Financeiro")
try:
    with conn.session as s:
        df_vendas = pd.read_sql(text("SELECT * FROM vendas"), s.bind)

    if not df_vendas.empty:
        df_vendas['data_venda'] = pd.to_datetime(df_vendas['data_venda'])
        hoje = pd.Timestamp.now(tz='UTC').normalize()
        df_hoje = df_vendas[df_vendas['data_venda'] >= hoje]

        st.caption("**Total Geral**")
        col1, col2, col3, col4 = st.columns(4)
        total_bruto  = float(df_vendas['valor_bruto'].sum())
        total_liq    = float(df_vendas['valor_liquido'].sum())
        total_taxas  = total_bruto - total_liq
        ticket_medio = total_bruto / len(df_vendas)

        col1.metric("Faturamento Bruto",  f"R$ {total_bruto:,.2f}")
        col2.metric("Lucro Líquido",      f"R$ {total_liq:,.2f}")
        col3.metric("Total em Taxas",     f"R$ {total_taxas:,.2f}", delta=f"-R$ {total_taxas:,.2f}", delta_color="inverse")
        col4.metric("Ticket Médio",       f"R$ {ticket_medio:,.2f}")

        if not df_hoje.empty:
            st.caption("**Hoje**")
            c1, c2, c3 = st.columns(3)
            c1.metric("Vendas Hoje",   f"R$ {float(df_hoje['valor_bruto'].sum()):,.2f}")
            c2.metric("Líquido Hoje",  f"R$ {float(df_hoje['valor_liquido'].sum()):,.2f}")
            c3.metric("Nº de Vendas",  len(df_hoje))
        else:
            st.info("Nenhuma venda registrada hoje ainda.")

        st.divider()

        col_g1, col_g2 = st.columns(2)

        with col_g1:
            fig_pizza = px.pie(
                df_vendas, values='valor_bruto', names='metodo_pagamento',
                title="Distribuição por Forma de Pagamento", hole=0.4
            )
            st.plotly_chart(fig_pizza, use_container_width=True)

        with col_g2:
            df_vendas['dia'] = df_vendas['data_venda'].dt.date
            df_por_dia = df_vendas.groupby('dia')['valor_bruto'].sum().reset_index()
            df_por_dia.columns = ['Data', 'Faturamento']
            fig_barra = px.bar(
                df_por_dia.tail(30), x='Data', y='Faturamento',
                title="Faturamento Diário (últimos 30 dias)", labels={'Faturamento': 'R$'}
            )
            st.plotly_chart(fig_barra, use_container_width=True)
    else:
        st.info("Nenhuma venda registrada no sistema ainda.")
except Exception as e:
    st.error(f"Erro ao carregar vendas: {e}")

# --- TOP PRODUTOS (via itens_venda) ---
st.divider()
st.subheader("🏆 Produtos Mais Vendidos")
try:
    with conn.session as s:
        df_top = pd.read_sql(
            text("""
                SELECT p.nome AS produto,
                       SUM(iv.quantidade)                     AS total_vendido,
                       SUM(iv.quantidade * iv.preco_unitario) AS receita
                FROM itens_venda iv
                JOIN produtos p ON p.id = iv.produto_id
                GROUP BY p.nome
                ORDER BY total_vendido DESC
                LIMIT 10
            """),
            s.bind
        )

    if not df_top.empty:
        fig_top = px.bar(
            df_top, x='produto', y='total_vendido',
            title="Top 10 Produtos por Quantidade Vendida",
            labels={'total_vendido': 'Qtd Vendida', 'produto': 'Produto'},
            color='receita', color_continuous_scale='Greens'
        )
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info("Ainda sem dados para ranking de produtos.")
except Exception as e:
    st.error(f"Erro ao carregar ranking: {e}")