import streamlit as st
import pandas as pd
from sqlalchemy import text
import plotly.express as px

st.set_page_config(page_title="Dashboard VIP", layout="wide")
conn = st.connection("postgresql", type="sql")

# --- SIDEBAR COM LOGO ---
st.sidebar.image("free_icon_1 (1).svg", width=100)
st.sidebar.divider()

st.title("📊 Inteligência de Negócio")

# --- FILTRO DE PERÍODO ---
periodo = st.selectbox(
    "Período de Análise", 
    options=["7 dias", "15 dias", "30 dias", "Todo o histórico"],
    index=2
)
dias_map = {"7 dias": 7, "15 dias": 15, "30 dias": 30, "Todo o histórico": 9999}
dias = dias_map[periodo]

# --- 1. CARREGAMENTO DE DADOS (BI AVANÇADO) ---
try:
    with conn.session as s:
        # Métricas Financeiras
        query_finc = text(f"""
            SELECT 
                SUM(valor_bruto) as bruto, 
                SUM(valor_liquido) as liquido, 
                COUNT(id) as total_vendas
            FROM vendas 
            WHERE data_venda >= CURRENT_DATE - INTERVAL '{dias} days'
        """)
        df_finc = pd.read_sql(query_finc, s.bind)

        # Métrica: Novos Clientes (VIP)
        query_cli = text(f"""
            SELECT COUNT(id) as novos_clientes 
            FROM clientes 
            WHERE created_at >= CURRENT_DATE - INTERVAL '{dias} days'
        """)
        novos_cli = s.execute(query_cli).fetchone()[0] or 0

        # Gráfico: Faturamento por Canal (VIP)
        query_canais = text(f"""
            SELECT canal_venda, SUM(valor_bruto) as total
            FROM vendas
            WHERE data_venda >= CURRENT_DATE - INTERVAL '{dias} days'
            GROUP BY canal_venda
        """)
        df_canais = pd.read_sql(query_canais, s.bind)

        # Gráfico: Vendas por Dia
        query_vendas_dia = text(f"""
            SELECT date_trunc('day', data_venda) as dia, SUM(valor_bruto) as total 
            FROM vendas 
            WHERE data_venda >= CURRENT_DATE - INTERVAL '{dias} days' 
            GROUP BY dia ORDER BY dia
        """)
        df_vendas_dia = pd.read_sql(query_vendas_dia, s.bind)

        # Ranking: Top 5 Produtos
        query_top_prod = text(f"""
            SELECT p.nome, SUM(i.quantidade) as qtd 
            FROM itens_venda i 
            JOIN produtos p ON i.produto_id = p.id 
            JOIN vendas v ON i.venda_id = v.id 
            WHERE v.data_venda >= CURRENT_DATE - INTERVAL '{dias} days' 
            GROUP BY p.nome ORDER BY qtd DESC LIMIT 5
        """)
        df_top_prod = pd.read_sql(query_top_prod, s.bind)

# --- 2. EXIBIÇÃO DE MÉTRICAS ---
    m1, m2, m3, m4 = st.columns(4)
    bruto = df_finc['bruto'].iloc[0] or 0
    liquido = df_finc['liquido'].iloc[0] or 0
    
    m1.metric("Faturamento Bruto", f"R$ {bruto:,.2f}")
    m2.metric("Líquido (Pós Taxas)", f"R$ {liquido:,.2f}")
    m3.metric("Novos Clientes", f"+{novos_cli}")
    m4.metric("Total de Vendas", int(df_finc['total_vendas'].iloc[0] or 0))

    st.divider()

# --- 3. GRÁFICOS PRINCIPAIS ---
    col_a, col_b = st.columns([2, 1])

    with col_a:
        st.subheader("📈 Histórico de Faturamento")
        if not df_vendas_dia.empty:
            fig_evolucao = px.area(df_vendas_dia, x='dia', y='total', color_discrete_sequence=['#00CC96'])
            st.plotly_chart(fig_evolucao, use_container_width=True)
    
    with col_b:
        st.subheader("🎯 Vendas por Canal")
        if not df_canais.empty:
            fig_pizza = px.pie(df_canais, values='total', names='canal_venda', hole=0.4,
                               color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pizza, use_container_width=True)

    st.divider()

# --- 4. SEGUNDA LINHA DE INSIGHTS ---
    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("🏆 Produtos Mais Vendidos")
        if not df_top_prod.empty:
            fig_top = px.bar(df_top_prod, x='qtd', y='nome', orientation='h', 
                             color='qtd', color_continuous_scale='Greens')
            st.plotly_chart(fig_top, use_container_width=True)
    
    with col_d:
        st.subheader("ℹ️ Insights de Consultoria")
        st.info(f"""
        **Resumo do Período:**
        * O canal **{df_canais.loc[df_canais['total'].idxmax(), 'canal_venda'] if not df_canais.empty else 'N/A'}** é o mais rentável.
        * Você atraiu **{novos_cli}** novos clientes potenciais para fidelizar.
        * A taxa média de perda por maquininha é de **{((bruto-liquido)/bruto*100) if bruto > 0 else 0:.1f}%**.
        """)

except Exception as e:
    st.error(f"Erro ao carregar o Dashboard: {e}")