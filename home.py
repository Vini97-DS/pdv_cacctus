import streamlit as st
import pandas as pd
from sqlalchemy import text
import plotly.express as px

st.set_page_config(page_title="Dashboard de Gestão", layout="wide")
conn = st.connection("postgresql", type="sql")

st.title("📊 Dashboard de Inteligência")

# --- 1. CARREGAMENTO DE DADOS (BI) ---
try:
    with conn.session as s:
        # Métricas Gerais (Últimos 30 dias)
        query_metrics = text("""
            SELECT 
                SUM(valor_bruto) as total_bruto,
                SUM(valor_liquido) as total_liquido,
                AVG(valor_bruto) as ticket_medio,
                COUNT(id) as total_vendas
            FROM vendas
            WHERE data_venda >= CURRENT_DATE - INTERVAL '30 days'
        """)
        metrics_df = pd.read_sql(query_metrics, s.bind)

        # Alerta de Inventário
        query_estoque = text("""
            SELECT nome, estoque_atual, estoque_minimo 
            FROM produtos 
            WHERE estoque_atual <= estoque_minimo
        """)
        estoque_alerta_df = pd.read_sql(query_estoque, s.bind)

        # Ranking de Marcas (A novidade para o Pitch!)
        query_marcas = text("""
            SELECT 
                p.marca, 
                SUM(i.quantidade * i.preco_unitario) as faturamento_total,
                SUM(i.quantidade) as qtd_vendida
            FROM itens_venda i
            JOIN produtos p ON i.produto_id = p.id
            GROUP BY p.marca
            ORDER BY faturamento_total DESC
        """)
        df_marcas = pd.read_sql(query_marcas, s.bind)

# --- 2. EXIBIÇÃO DE MÉTRICAS NO TOPO ---
    col1, col2, col3, col4 = st.columns(4)
    
    bruto = metrics_df['total_bruto'].iloc[0] or 0
    liquido = metrics_df['total_liquido'].iloc[0] or 0
    t_medio = metrics_df['ticket_medio'].iloc[0] or 0
    vendas_qtd = metrics_df['total_vendas'].iloc[0] or 0

    col1.metric("Faturamento (30d)", f"R$ {bruto:,.2f}")
    col2.metric("Lucro Líquido (30d)", f"R$ {liquido:,.2f}", delta=f"Taxas: R$ {(bruto-liquido):,.2f}", delta_color="inverse")
    col3.metric("Ticket Médio", f"R$ {t_medio:,.2f}")
    col4.metric("Qtd de Vendas", int(vendas_qtd))

# --- 3. ALERTAS CRÍTICOS ---
    if not estoque_alerta_df.empty:
        st.warning(f"⚠️ **Atenção:** Você tem {len(estoque_alerta_df)} produtos abaixo do estoque mínimo!")
        with st.expander("Ver produtos para reposição"):
            st.table(estoque_alerta_df)

    st.divider()

# --- 4. GRÁFICOS DE DESEMPENHO POR MARCA ---
    st.subheader("🏷️ Análise de Performance por Marca")
    
    if not df_marcas.empty:
        df_marcas['marca'] = df_marcas['marca'].fillna('Sem Marca')
        
        c1, c2 = st.columns([3, 2])

        # Gráfico de Barras: Faturamento por Marca
        fig_bar = px.bar(
            df_marcas, 
            x='marca', 
            y='faturamento_total',
            title='Faturamento Total por Marca (R$)',
            text_auto='.2s',
            color='faturamento_total',
            color_continuous_scale='Blues'
        )
        c1.plotly_chart(fig_bar, use_container_width=True)

        # Gráfico de Rosca: Participação no Volume de Vendas
        fig_pie = px.pie(
            df_marcas, 
            values='qtd_vendida', 
            names='marca', 
            title='Volume de Saída (Qtd)',
            hole=0.5
        )
        c2.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Aguardando primeiras vendas para gerar análise de marcas.")

# --- 5. TABELA DE VENDAS RECENTES ---
    st.divider()
    st.subheader("🕒 Vendas Diárias Recentes")
    query_recentes = text("SELECT data_venda, valor_bruto, metodo_pagamento FROM vendas ORDER BY data_venda DESC LIMIT 10")
    recentes_df = pd.read_sql(query_recentes, s.bind)
    st.dataframe(recentes_df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Erro ao carregar o Dashboard: {e}")