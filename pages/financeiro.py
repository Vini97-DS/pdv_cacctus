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
        vendas_hoje = s.execute(text("SELECT SUM(valor_bruto) FROM vendas WHERE data_venda::date = CURRENT_DATE")).fetchone()[0] or 0
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

# --- TAB: SAÍDA SIMPLIFICADA ---
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

# --- TAB: COMPRA DE MERCADORIA (CADASTRO HÍBRIDO) ---
with tab_compra:
    st.subheader("Registrar Entrada ou Novo Produto")
    try:
        with conn.session as s:
            df_prods = pd.read_sql(text("SELECT id, nome, fator_conversao FROM produtos ORDER BY nome"), s.bind)
        
        # Opções do selectbox incluindo a opção de novo cadastro
        opcoes_prods = ["+ CADASTRAR NOVO PRODUTO"] + df_prods['nome'].tolist()
        escolha = st.selectbox("Selecione o Produto ou Cadastre um Novo", opcoes_prods)

        with st.form("form_compra_estoque", clear_on_submit=True):
            if escolha == "+ CADASTRAR NOVO PRODUTO":
                st.info("✨ Você está cadastrando um novo item no estoque via Financeiro.")
                nome_novo = st.text_input("Nome do Novo Produto")
                marca_novo = st.text_input("Marca")
                cat_novo = st.selectbox("Categoria", ["Essencia", "Carvão", "Bebidas", "Comidas", "Acessórios", "Outros"])
                fator_novo = st.number_input("Fator de Conversão (Ex: 60 se a caixa vem com 60 unidades)", min_value=1, value=1)
                p_venda_sugerido = st.number_input("Preço de Venda Final (R$)", min_value=0.0, step=0.1)
            else:
                st.write(f"📦 Lançando entrada para: **{escolha}**")
            
            st.divider()
            c1, c2, c3 = st.columns([1, 1, 1])
            qtd_vol = c1.number_input("Qtd comprada", min_value=1, step=1)
            tipo_un = c2.selectbox("Formato", ["Unidades", "Caixas", "Pacotes"])
            total_pago = c3.number_input("Valor Total Pago (R$)", min_value=0.0, step=0.01)

            if st.form_submit_button("Confirmar Compra e Salvar", type="primary", width='stretch'):
                try:
                    with conn.session as s:
                        # 1. Se for produto novo, insere primeiro na tabela produtos
                        if escolha == "+ CADASTRAR NOVO PRODUTO":
                            if not nome_novo:
                                st.error("Nome do produto é obrigatório!")
                                st.stop()
                            
                            res = s.execute(
                                text("""
                                    INSERT INTO produtos (nome, marca, categoria, fator_conversao, preco_venda, estoque_atual, estoque_minimo)
                                    VALUES (:n, :m, :cat, :f, :pv, 0, 5) RETURNING id, fator_conversao
                                """),
                                {"n": nome_novo, "m": marca_novo, "cat": cat_novo, "f": fator_novo, "pv": p_venda_sugerido}
                            )
                            row = res.fetchone()
                            p_id, p_fator = row[0], row[1]
                            p_nome_final = nome_novo
                        else:
                            # Se já existe, pega os dados do DF
                            p_info = df_prods[df_prods['nome'] == escolha].iloc[0]
                            p_id, p_fator = p_info['id'], p_info['fator_conversao']
                            p_nome_final = escolha

                        # 2. Lógica de cálculo
                        fator_final = p_fator if tipo_un != "Unidades" else 1
                        qtd_final = qtd_vol * fator_final
                        custo_un = total_pago / qtd_final if qtd_final > 0 else 0

                        # 3. Registra Saída no Financeiro
                        s.execute(
                            text("INSERT INTO financeiro (descricao, valor, categoria, data_gasto) VALUES (:d, :v, 'Compra de Estoque', CURRENT_DATE)"),
                            {"d": f"Compra: {qtd_vol} {tipo_un} de {p_nome_final}", "v": float(total_pago)}
                        )

                        # 4. Atualiza Estoque e Custo
                        s.execute(
                            text("UPDATE produtos SET estoque_atual = estoque_atual + :q, preco_custo = :pc WHERE id = :id"),
                            {"q": int(qtd_final), "pc": float(custo_un), "id": p_id}
                        )
                        s.commit()
                    
                    st.success(f"✅ {p_nome_final} atualizado! +{qtd_final} unidades no estoque.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro no processamento: {e}")
    except Exception as e:
        st.info("Aguardando carregamento de produtos...")