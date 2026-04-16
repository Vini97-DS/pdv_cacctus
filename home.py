import streamlit as st
import pandas as pd
from sqlalchemy import text
import plotly.express as px

st.set_page_config(page_title="Dashboard de Gestão", layout="wide")
conn = st.connection("postgresql", type="sql")

st.title("Dashboard de Inteligência para o Negócio")

# --- FILTRO DE PERÍODO  ---
periodo = st.selectbox(
    "Filtrar Período", 
    options=["7 dias", "15 dias", "30 dias", "Todo o histórico"],
    index=3
)
dias_map = {"7 dias": 7, "15 dias": 15, "30 dias": 30, "Todo o histórico": 9999}
dias = dias_map[periodo]

# --- 1. CARREGAMENTO DE DADOS ---
try:
    with conn.session as s:
        # Métricas (Faturamento, Líquido, etc)
        metrics_df = pd.read_sql(text(f"SELECT SUM(valor_bruto) as bruto, SUM(valor_liquido) as liquido, AVG(valor_bruto) as ticket, COUNT(id) as vendas FROM vendas WHERE data_venda >= CURRENT_DATE - INTERVAL '{dias} days'"), s.bind)
        
        # Alerta de Estoque
        estoque_df = pd.read_sql(text("SELECT nome, estoque_atual, estoque_minimo FROM produtos"), s.bind)
        
        # Vendas Diárias
        vendas_dia_df = pd.read_sql(text(f"SELECT date_trunc('day', data_venda) as dia, SUM(valor_bruto) as total FROM vendas WHERE data_venda >= CURRENT_DATE - INTERVAL '{dias} days' GROUP BY dia ORDER BY dia"), s.bind)
        
        # Meios de Pagamento
        pagto_df = pd.read_sql(text(f"SELECT metodo_pagamento, COUNT(*) as qtd FROM vendas WHERE data_venda >= CURRENT_DATE - INTERVAL '{dias} days' GROUP BY metodo_pagamento"), s.bind)
        
        # Marcas
        marcas_df = pd.read_sql(text(f"SELECT p.marca, SUM(i.quantidade * i.preco_unitario) as faturamento FROM itens_venda i JOIN produtos p ON i.produto_id = p.id JOIN vendas v ON i.venda_id = v.id WHERE v.data_venda >= CURRENT_DATE - INTERVAL '{dias} days' GROUP BY p.marca ORDER BY faturamento DESC"), s.bind)
        
        # Top 5 Produtos
        top_prod_df = pd.read_sql(text(f"SELECT p.nome, SUM(i.quantidade) as qtd FROM itens_venda i JOIN produtos p ON i.produto_id = p.id JOIN vendas v ON i.venda_id = v.id WHERE v.data_venda >= CURRENT_DATE - INTERVAL '{dias} days' GROUP BY p.nome ORDER BY qtd DESC LIMIT 5"), s.bind)

# --- 2. MÉTRICAS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Faturamento", f"R$ {metrics_df['bruto'].iloc[0] or 0:,.2f}")
    c2.metric("Líquido", f"R$ {metrics_df['liquido'].iloc[0] or 0:,.2f}")
    c3.metric("Ticket Médio", f"R$ {metrics_df['ticket'].iloc[0] or 0:,.2f}")
    c4.metric("Vendas", int(metrics_df['vendas'].iloc[0] or 0))

# --- 3. ALERTA DE ESTOQUE (BANNER DINÂMICO) ---
    st.write("") # Espaçamento
    itens_zerados = estoque_df[estoque_df['estoque_atual'] <= 0]
    itens_atencao = estoque_df[(estoque_df['estoque_atual'] > 0) & (estoque_df['estoque_atual'] <= estoque_df['estoque_minimo'])]

    if not itens_zerados.empty:
        st.error(f"🚨 **ESTOQUE ZERADO:** {', '.join(itens_zerados['nome'].tolist())}")
    elif not itens_atencao.empty:
        st.warning(f"⚠️ **ATENÇÃO (Reposição):** {', '.join(itens_atencao['nome'].tolist())}")
    else:
        st.success("✅ **TUDO OK:** Todos os produtos com estoque saudável.")

    st.divider()

# --- 4. LINHA: FATURAMENTO DIÁRIO + MEIOS DE PAGAMENTO ---
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        st.subheader("Faturamento Diário")
        if not vendas_dia_df.empty:
            fig_linha = px.line(vendas_dia_df, x='dia', y='total', markers=True, color_discrete_sequence=['#00CC96'])
            fig_linha.update_layout(margin=dict(l=0, r=0, t=30, b=0), height=280)
            st.plotly_chart(fig_linha, use_container_width=True)
            
    with col_b:
        st.subheader("Meios de Pagamento")
        if not pagto_df.empty:
            fig_pizza = px.pie(pagto_df, values='qtd', names='metodo_pagamento', hole=0.3)
            fig_pizza.update_layout(margin=dict(l=0, r=0, t=30, b=0), height=300)
            st.plotly_chart(fig_pizza, use_container_width=True)

    st.divider()

# --- 5. LINHA: MARCAS + TOP 5 PRODUTOS ---
    col_c, col_d = st.columns([2, 1])

    with col_c:
        st.subheader("Faturamento por Marca")
        if not marcas_df.empty:
            marcas_df['marca'] = marcas_df['marca'].fillna('Sem Marca')
            fig_marcas = px.bar(marcas_df, x='marca', y='faturamento', color='faturamento', color_continuous_scale='greens')
            fig_marcas.update_layout(margin=dict(l=0, r=0, t=30, b=0), height=300)
            st.plotly_chart(fig_marcas, use_container_width=True)

    with col_d:
        st.subheader("Top 5 Produtos mais Vendidos")
        if not top_prod_df.empty:
            fig_top = px.bar(top_prod_df, x='qtd', y='nome', orientation='h', color_discrete_sequence=["#036628"])
            fig_top.update_layout(margin=dict(l=0, r=0, t=30, b=0), height=350, yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_top, use_container_width=True)

except Exception as e:
    st.error(f"Erro ao carregar Dashboard: {e}")