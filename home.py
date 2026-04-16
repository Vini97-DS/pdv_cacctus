import streamlit as st
import pandas as pd
from sqlalchemy import text
import plotly.express as px

st.set_page_config(page_title="Dashboard de Gestão", layout="wide")
conn = st.connection("postgresql", type="sql")

st.title("📊 Dashboard de Inteligência")

# --- 1. FILTRO DE PERÍODO (TOP) ---
periodo = st.selectbox(
    "Filtrar Período", 
    options=["7 dias", "15 dias", "30 dias", "Todo o histórico"],
    index=2 # Padrão 30 dias
)

# Lógica de dias para a Query
dias_map = {"7 dias": 7, "15 dias": 15, "30 dias": 30, "Todo o histórico": 9999}
dias = dias_map[periodo]

# --- 2. CARREGAMENTO DE DADOS ---
try:
    with conn.session as s:
        # Métricas Gerais
        query_metrics = text(f"""
            SELECT 
                SUM(valor_bruto) as total_bruto,
                SUM(valor_liquido) as total_liquido,
                AVG(valor_bruto) as ticket_medio,
                COUNT(id) as total_vendas
            FROM vendas
            WHERE data_venda >= CURRENT_DATE - INTERVAL '{dias} days'
        """)
        metrics_df = pd.read_sql(query_metrics, s.bind)

        # Gráfico: Vendas por Dia
        query_vendas_dia = text(f"""
            SELECT date_trunc('day', data_venda) as dia, SUM(valor_bruto) as total
            FROM vendas
            WHERE data_venda >= CURRENT_DATE - INTERVAL '{dias} days'
            GROUP BY dia ORDER BY dia
        """)
        vendas_dia_df = pd.read_sql(query_vendas_dia, s.bind)

        # Ranking: Produtos Mais Vendidos
        query_ranking_prod = text(f"""
            SELECT p.nome, SUM(i.quantidade) as qtd
            FROM itens_venda i
            JOIN produtos p ON i.produto_id = p.id
            JOIN vendas v ON i.venda_id = v.id
            WHERE v.data_venda >= CURRENT_DATE - INTERVAL '{dias} days'
            GROUP BY p.nome ORDER BY qtd DESC LIMIT 10
        """)
        ranking_prod_df = pd.read_sql(query_ranking_prod, s.bind)

        # Ranking: Marcas
        query_marcas = text(f"""
            SELECT p.marca, SUM(i.quantidade * i.preco_unitario) as faturamento
            FROM itens_venda i
            JOIN produtos p ON i.produto_id = p.id
            JOIN vendas v ON i.venda_id = v.id
            WHERE v.data_venda >= CURRENT_DATE - INTERVAL '{dias} days'
            GROUP BY p.marca ORDER BY faturamento DESC
        """)
        df_marcas = pd.read_sql(query_marcas, s.bind)

        # Alerta de Estoque (Sempre mostra independente da data)
        query_estoque = text("SELECT nome, estoque_atual, estoque_minimo FROM produtos WHERE estoque_atual <= estoque_minimo")
        estoque_alerta_df = pd.read_sql(query_estoque, s.bind)

# --- 3. EXIBIÇÃO ---
    col1, col2, col3, col4 = st.columns(4)
    bruto = metrics_df['total_bruto'].iloc[0] or 0
    liquido = metrics_df['total_liquido'].iloc[0] or 0
    t_medio = metrics_df['ticket_medio'].iloc[0] or 0
    v_qtd = metrics_df['total_vendas'].iloc[0] or 0

    col1.metric("Faturamento", f"R$ {bruto:,.2f}")
    col2.metric("Líquido", f"R$ {liquido:,.2f}")
    col3.metric("Ticket Médio", f"R$ {t_medio:,.2f}")
    col4.metric("Vendas", int(v_qtd))

    st.divider()

    # Linha 1 de Gráficos: Vendas no Tempo e Alerta
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("📈 Faturamento Diário")
        if not vendas_dia_df.empty:
            fig_vendas = px.line(vendas_dia_df, x='dia', y='total', markers=True, color_discrete_sequence=['#00CC96'])
            st.plotly_chart(fig_vendas, use_container_width=True)
        else:
            st.info("Sem vendas no período.")

    with c2:
        st.subheader("⚠️ Estoque Crítico")
        if not estoque_alerta_df.empty:
            st.dataframe(estoque_alerta_df, hide_index=True)
        else:
            st.success("Estoque em dia!")

    st.divider()

    # Linha 2 de Gráficos: Produtos e Marcas
    c3, c4 = st.columns(2)

    with c3:
        st.subheader("🏆 Top 10 Produtos")
        if not ranking_prod_df.empty:
            fig_rank = px.bar(ranking_prod_df, x='qtd', y='nome', orientation='h', color='qtd', color_continuous_scale='Reds')
            st.plotly_chart(fig_rank, use_container_width=True)

    with c4:
        st.subheader("🏷️ Faturamento por Marca")
        if not df_marcas.empty:
            df_marcas['marca'] = df_marcas['marca'].fillna('Sem Marca')
            fig_marca = px.pie(df_marcas, values='faturamento', names='marca', hole=0.4)
            st.plotly_chart(fig_marca, use_container_width=True)

except Exception as e:
    st.error(f"Erro no Dashboard: {e}")