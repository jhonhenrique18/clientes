import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np

# Configuração da página
st.set_page_config(
    page_title="Análise de Clientes Novos",
    page_icon="👥",
    layout="wide"
)

@st.cache_data
def carregar_dados():
    """Carrega e processa os dados de vendas"""
    # Tentativas de encoding
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            # Lendo o arquivo
            df = pd.read_csv("Vendas até 24-07-2025.txt", 
                            sep=";", 
                            encoding=encoding,
                            on_bad_lines='skip')
            
            # Se chegou até aqui, o encoding funcionou
            break
            
        except UnicodeDecodeError:
            continue
        except Exception as e:
            if encoding == encodings[-1]:  # último encoding
                st.error(f"Erro ao carregar dados: {e}")
                return pd.DataFrame()
            continue
    
    try:
        # Verificando se temos colunas suficientes
        if len(df.columns) < 15:
            st.error(f"Arquivo com estrutura inválida. Colunas encontradas: {len(df.columns)}")
            return pd.DataFrame()
        
        # Renomeando colunas principais
        df.columns = [
            'Data_Competencia', 'Hora', 'N_Venda', 'N_NF', 'Codigo_Cliente', 
            'Nome_Cliente', 'Quantidade', 'Valor', 'Acrescimo', 'Desconto', 
            'Total', 'Desp_Acess', 'Valor_Frete_CIF', 'Valor_Seguro', 
            'Total_Venda', 'Percentual_Desc', 'Total_Preco_Base'
        ] + [f'col_{i}' for i in range(17, len(df.columns))]
        
        # Convertendo data
        df['Data_Competencia'] = pd.to_datetime(df['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
        
        # Convertendo valores numéricos
        df['Total_Venda'] = pd.to_numeric(df['Total_Venda'].astype(str).str.replace(',', '.'), errors='coerce')
        
        # Filtrando apenas vendas válidas
        df = df[df['Data_Competencia'].notna()]
        df = df[df['Nome_Cliente'].notna()]
        df = df[~df['Nome_Cliente'].str.contains('DEVOLUCAO', na=False)]
        df = df[df['Total_Venda'] > 0]  # Apenas valores positivos
        
        # Adicionando colunas de análise
        df['Ano_Mes'] = df['Data_Competencia'].dt.to_period('M')
        df['Mes'] = df['Data_Competencia'].dt.month
        df['Nome_Mes'] = df['Data_Competencia'].dt.strftime('%B')
        df['Ano'] = df['Data_Competencia'].dt.year
        
        return df.dropna(subset=['Data_Competencia', 'Nome_Cliente'])
        
    except Exception as e:
        st.error(f"Erro ao processar dados: {e}")
        return pd.DataFrame()

def identificar_clientes_novos(df):
    """Identifica clientes novos por mês"""
    # Primeira compra de cada cliente
    primeira_compra = df.groupby('Nome_Cliente')['Data_Competencia'].min().reset_index()
    primeira_compra.columns = ['Nome_Cliente', 'Data_Primeira_Compra']
    primeira_compra['Mes_Primeira_Compra'] = primeira_compra['Data_Primeira_Compra'].dt.to_period('M')
    
    # Juntando com dados de vendas
    df_com_primeira = df.merge(primeira_compra, on='Nome_Cliente')
    
    # Identificando vendas da primeira compra
    df_primeira_compra = df_com_primeira[
        df_com_primeira['Data_Competencia'] == df_com_primeira['Data_Primeira_Compra']
    ]
    
    return primeira_compra, df_primeira_compra

def analise_por_mes(primeira_compra, df_primeira_compra):
    """Análise de clientes novos por mês"""
    # Contagem de clientes novos por mês
    clientes_por_mes = primeira_compra.groupby('Mes_Primeira_Compra').size().reset_index()
    clientes_por_mes.columns = ['Mes', 'Quantidade_Clientes_Novos']
    clientes_por_mes['Mes_Nome'] = clientes_por_mes['Mes'].astype(str)
    
    # Média gasta na primeira compra por mês
    media_gasta = df_primeira_compra.groupby(
        df_primeira_compra['Data_Primeira_Compra'].dt.to_period('M')
    )['Total_Venda'].mean().reset_index()
    media_gasta.columns = ['Mes', 'Media_Primeira_Compra']
    media_gasta['Mes_Nome'] = media_gasta['Mes'].astype(str)
    
    # Lista de clientes novos por mês
    lista_clientes = primeira_compra.groupby('Mes_Primeira_Compra')['Nome_Cliente'].apply(list).reset_index()
    lista_clientes.columns = ['Mes', 'Lista_Clientes']
    lista_clientes['Mes_Nome'] = lista_clientes['Mes'].astype(str)
    
    return clientes_por_mes, media_gasta, lista_clientes

def layout_desktop(df, primeira_compra, df_primeira_compra, clientes_por_mes, media_gasta, lista_clientes):
    """Layout otimizado para desktop"""
    # Métricas gerais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_clientes = len(primeira_compra)
        st.metric("Total de Clientes", total_clientes)
    
    with col2:
        clientes_julho = len(primeira_compra[primeira_compra['Mes_Primeira_Compra'] == '2025-07'])
        st.metric("Novos em Julho", clientes_julho)
    
    with col3:
        if not df_primeira_compra.empty:
            media_geral = df_primeira_compra['Total_Venda'].mean()
            st.metric("Média 1ª Compra", f"R$ {media_geral:,.2f}")
    
    with col4:
        periodo = f"{df['Data_Competencia'].min().strftime('%b/%Y')} - {df['Data_Competencia'].max().strftime('%b/%Y')}"
        st.metric("Período", periodo)
    
    st.markdown("---")
    
    # Gráficos lado a lado
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Clientes Novos por Mês")
        if not clientes_por_mes.empty:
            fig1 = px.bar(
                clientes_por_mes,
                x='Mes_Nome',
                y='Quantidade_Clientes_Novos',
                title="Quantidade de Clientes Novos por Mês",
                labels={'Mes_Nome': 'Mês', 'Quantidade_Clientes_Novos': 'Quantidade'},
                color='Quantidade_Clientes_Novos',
                color_continuous_scale='Blues'
            )
            fig1.update_layout(showlegend=False)
            st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.subheader("💰 Média da Primeira Compra")
        if not media_gasta.empty:
            fig2 = px.line(
                media_gasta,
                x='Mes_Nome',
                y='Media_Primeira_Compra',
                title="Média Gasta na Primeira Compra por Mês",
                labels={'Mes_Nome': 'Mês', 'Media_Primeira_Compra': 'Média (R$)'},
                markers=True
            )
            fig2.update_traces(line_color='green', marker_color='green')
            st.plotly_chart(fig2, use_container_width=True)

def layout_mobile(df, primeira_compra, df_primeira_compra, clientes_por_mes, media_gasta, lista_clientes):
    """Layout otimizado para mobile"""
    # Métricas em duas colunas para mobile
    col1, col2 = st.columns(2)
    
    with col1:
        total_clientes = len(primeira_compra)
        st.metric("Total de Clientes", total_clientes)
        
        clientes_julho = len(primeira_compra[primeira_compra['Mes_Primeira_Compra'] == '2025-07'])
        st.metric("Novos em Julho", clientes_julho)
    
    with col2:
        if not df_primeira_compra.empty:
            media_geral = df_primeira_compra['Total_Venda'].mean()
            st.metric("Média 1ª Compra", f"R$ {media_geral:,.2f}")
        
        periodo = f"{df['Data_Competencia'].min().strftime('%b/%Y')} - {df['Data_Competencia'].max().strftime('%b/%Y')}"
        st.metric("Período", periodo)
    
    st.markdown("---")
    
    # Gráficos empilhados para mobile
    st.subheader("📈 Clientes Novos por Mês")
    if not clientes_por_mes.empty:
        fig1 = px.bar(
            clientes_por_mes,
            x='Mes_Nome',
            y='Quantidade_Clientes_Novos',
            title="Quantidade de Clientes Novos por Mês",
            labels={'Mes_Nome': 'Mês', 'Quantidade_Clientes_Novos': 'Quantidade'},
            color='Quantidade_Clientes_Novos',
            color_continuous_scale='Blues'
        )
        fig1.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig1, use_container_width=True)
    
    st.subheader("💰 Média da Primeira Compra")
    if not media_gasta.empty:
        fig2 = px.line(
            media_gasta,
            x='Mes_Nome',
            y='Media_Primeira_Compra',
            title="Média Gasta na Primeira Compra por Mês",
            labels={'Mes_Nome': 'Mês', 'Media_Primeira_Compra': 'Média (R$)'},
            markers=True
        )
        fig2.update_traces(line_color='green', marker_color='green')
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)

def analise_geral_clientes(df, layout_mode):
    """Análise completa de todos os clientes"""
    st.title("👥 Análise Geral de Clientes - Grãos S.A.")
    st.markdown("*Segmentação estratégica e análise completa da base de clientes*")
    
    # Preparando dados para análise geral
    clientes_resumo = df.groupby('Nome_Cliente').agg({
        'Total_Venda': ['sum', 'count', 'mean'],
        'Data_Competencia': ['min', 'max']
    }).reset_index()
    
    # Flatten column names
    clientes_resumo.columns = ['Nome_Cliente', 'Total_Faturamento', 'Quantidade_Compras', 'Ticket_Medio', 'Primeira_Compra', 'Ultima_Compra']
    
    # Calculando recência (dias desde última compra)
    data_atual = df['Data_Competencia'].max()
    clientes_resumo['Dias_Ultima_Compra'] = (data_atual - clientes_resumo['Ultima_Compra']).dt.days
    
    # Segmentação de clientes
    def classificar_cliente(row):
        if row['Total_Faturamento'] >= 1000 and row['Quantidade_Compras'] >= 5:
            return "🔥 VIP"
        elif row['Quantidade_Compras'] >= 3 and row['Dias_Ultima_Compra'] <= 30:
            return "🟢 Frequente"
        elif row['Dias_Ultima_Compra'] <= 60:
            return "🟡 Ocasional"
        else:
            return "🔵 Frio"
    
    clientes_resumo['Classificacao'] = clientes_resumo.apply(classificar_cliente, axis=1)
    
    # Métricas principais
    if layout_mode == "🖥️ Desktop":
        col1, col2, col3, col4, col5 = st.columns(5)
    else:
        col1, col2 = st.columns(2)
    
    with col1:
        total_clientes = len(clientes_resumo)
        st.metric("Total de Clientes", total_clientes)
    
    with col2:
        ticket_medio_geral = clientes_resumo['Ticket_Medio'].mean()
        st.metric("Ticket Médio Geral", f"R$ {ticket_medio_geral:,.2f}")
    
    if layout_mode == "🖥️ Desktop":
        with col3:
            clientes_vip = len(clientes_resumo[clientes_resumo['Classificacao'] == "🔥 VIP"])
            st.metric("Clientes VIP", clientes_vip)
        
        with col4:
            clientes_ativos = len(clientes_resumo[clientes_resumo['Dias_Ultima_Compra'] <= 30])
            st.metric("Clientes Ativos (30d)", clientes_ativos)
        
        with col5:
            faturamento_total = clientes_resumo['Total_Faturamento'].sum()
            st.metric("Faturamento Total", f"R$ {faturamento_total:,.2f}")
    else:
        # Mobile - segunda linha
        col3, col4 = st.columns(2)
        with col3:
            clientes_vip = len(clientes_resumo[clientes_resumo['Classificacao'] == "🔥 VIP"])
            st.metric("Clientes VIP", clientes_vip)
        
        with col4:
            clientes_ativos = len(clientes_resumo[clientes_resumo['Dias_Ultima_Compra'] <= 30])
            st.metric("Clientes Ativos (30d)", clientes_ativos)
        
        # Terceira linha para mobile
        faturamento_total = clientes_resumo['Total_Faturamento'].sum()
        st.metric("Faturamento Total", f"R$ {faturamento_total:,.2f}")
    
    st.markdown("---")
    
    # Gráficos de segmentação
    if layout_mode == "🖥️ Desktop":
        col1, col2 = st.columns(2)
    else:
        col1 = st.container()
        col2 = st.container()
    
    with col1:
        st.subheader("📊 Segmentação de Clientes")
        
        classificacao_count = clientes_resumo['Classificacao'].value_counts()
        fig1 = px.pie(
            values=classificacao_count.values,
            names=classificacao_count.index,
            title="Distribuição por Classificação"
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.subheader("💰 Top 10 Clientes por Faturamento")
        
        top_clientes = clientes_resumo.nlargest(10, 'Total_Faturamento')
        fig2 = px.bar(
            top_clientes,
            x='Total_Faturamento',
            y='Nome_Cliente',
            orientation='h',
            title="Maiores Faturamentos",
            labels={'Total_Faturamento': 'Faturamento (R$)', 'Nome_Cliente': 'Cliente'}
        )
        fig2.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig2, use_container_width=True)
    
    # Análise detalhada por classificação
    st.markdown("---")
    st.subheader("🔍 Análise Detalhada por Classificação")
    
    # Tabs para cada classificação
    tab1, tab2, tab3, tab4 = st.tabs(["🔥 VIP", "🟢 Frequentes", "🟡 Ocasionais", "🔵 Frios"])
    
    with tab1:
        vip_clientes = clientes_resumo[clientes_resumo['Classificacao'] == "🔥 VIP"].sort_values('Total_Faturamento', ascending=False)
        st.write(f"**{len(vip_clientes)} clientes VIP** - Respondem por R$ {vip_clientes['Total_Faturamento'].sum():,.2f}")
        
        if not vip_clientes.empty:
            st.dataframe(
                vip_clientes[['Nome_Cliente', 'Total_Faturamento', 'Quantidade_Compras', 'Ticket_Medio', 'Dias_Ultima_Compra']],
                column_config={
                    'Nome_Cliente': 'Cliente',
                    'Total_Faturamento': st.column_config.NumberColumn('Faturamento Total', format="R$ %.2f"),
                    'Quantidade_Compras': 'Nº Compras',
                    'Ticket_Medio': st.column_config.NumberColumn('Ticket Médio', format="R$ %.2f"),
                    'Dias_Ultima_Compra': 'Dias desde última compra'
                },
                use_container_width=True,
                hide_index=True
            )
    
    with tab2:
        freq_clientes = clientes_resumo[clientes_resumo['Classificacao'] == "🟢 Frequente"].sort_values('Quantidade_Compras', ascending=False)
        st.write(f"**{len(freq_clientes)} clientes frequentes** - Respondem por R$ {freq_clientes['Total_Faturamento'].sum():,.2f}")
        
        if not freq_clientes.empty:
            st.dataframe(
                freq_clientes[['Nome_Cliente', 'Total_Faturamento', 'Quantidade_Compras', 'Ticket_Medio', 'Dias_Ultima_Compra']],
                column_config={
                    'Nome_Cliente': 'Cliente',
                    'Total_Faturamento': st.column_config.NumberColumn('Faturamento Total', format="R$ %.2f"),
                    'Quantidade_Compras': 'Nº Compras',
                    'Ticket_Medio': st.column_config.NumberColumn('Ticket Médio', format="R$ %.2f"),
                    'Dias_Ultima_Compra': 'Dias desde última compra'
                },
                use_container_width=True,
                hide_index=True
            )
    
    with tab3:
        oca_clientes = clientes_resumo[clientes_resumo['Classificacao'] == "🟡 Ocasional"].sort_values('Total_Faturamento', ascending=False)
        st.write(f"**{len(oca_clientes)} clientes ocasionais** - Respondem por R$ {oca_clientes['Total_Faturamento'].sum():,.2f}")
        
        if not oca_clientes.empty:
            st.dataframe(
                oca_clientes[['Nome_Cliente', 'Total_Faturamento', 'Quantidade_Compras', 'Ticket_Medio', 'Dias_Ultima_Compra']],
                column_config={
                    'Nome_Cliente': 'Cliente',
                    'Total_Faturamento': st.column_config.NumberColumn('Faturamento Total', format="R$ %.2f"),
                    'Quantidade_Compras': 'Nº Compras',
                    'Ticket_Medio': st.column_config.NumberColumn('Ticket Médio', format="R$ %.2f"),
                    'Dias_Ultima_Compra': 'Dias desde última compra'
                },
                use_container_width=True,
                hide_index=True
            )
    
    with tab4:
        frio_clientes = clientes_resumo[clientes_resumo['Classificacao'] == "🔵 Frio"].sort_values('Dias_Ultima_Compra', ascending=False)
        st.write(f"**{len(frio_clientes)} clientes frios** - Última compra há mais de 60 dias")
        st.warning("💡 **Oportunidade:** Estes clientes podem precisar de ações de reativação!")
        
        if not frio_clientes.empty:
            st.dataframe(
                frio_clientes[['Nome_Cliente', 'Total_Faturamento', 'Quantidade_Compras', 'Ticket_Medio', 'Dias_Ultima_Compra']],
                column_config={
                    'Nome_Cliente': 'Cliente',
                    'Total_Faturamento': st.column_config.NumberColumn('Faturamento Total', format="R$ %.2f"),
                    'Quantidade_Compras': 'Nº Compras',
                    'Ticket_Medio': st.column_config.NumberColumn('Ticket Médio', format="R$ %.2f"),
                    'Dias_Ultima_Compra': 'Dias desde última compra'
                },
                use_container_width=True,
                hide_index=True
            )

def analise_clientes_novos(df, layout_mode):
    """Análise focada em clientes novos"""
    st.title("👶 Análise de Clientes Novos - Grãos S.A.")
    st.markdown("*Monitoramento de aquisição e performance de novos clientes*")
    
    # Identificando clientes novos
    primeira_compra, df_primeira_compra = identificar_clientes_novos(df)
    clientes_por_mes, media_gasta, lista_clientes = analise_por_mes(primeira_compra, df_primeira_compra)
    
    # Aplicar layout escolhido
    if layout_mode == "🖥️ Desktop":
        layout_desktop(df, primeira_compra, df_primeira_compra, clientes_por_mes, media_gasta, lista_clientes)
    else:
        layout_mobile(df, primeira_compra, df_primeira_compra, clientes_por_mes, media_gasta, lista_clientes)
    
    # Análise detalhada por mês (comum a ambos layouts)
    st.markdown("---")
    st.subheader("🔍 Análise Detalhada por Mês")
    
    # Tabela resumo
    if not clientes_por_mes.empty and not media_gasta.empty:
        resumo = clientes_por_mes.merge(media_gasta, on='Mes_Nome', how='outer').fillna(0)
        resumo['Media_Primeira_Compra'] = resumo['Media_Primeira_Compra'].round(2)
        
        st.dataframe(
            resumo[['Mes_Nome', 'Quantidade_Clientes_Novos', 'Media_Primeira_Compra']],
            column_config={
                'Mes_Nome': 'Mês',
                'Quantidade_Clientes_Novos': 'Novos Clientes',
                'Media_Primeira_Compra': st.column_config.NumberColumn(
                    'Média 1ª Compra (R$)',
                    format="R$ %.2f"
                )
            },
            use_container_width=True
        )
    
    # Análise detalhada de Julho
    st.markdown("---")
    st.subheader("🎯 Análise Detalhada - Julho 2025")
    
    clientes_julho_df = primeira_compra[primeira_compra['Mes_Primeira_Compra'] == '2025-07']
    
    if not clientes_julho_df.empty:
        vendas_julho = df_primeira_compra[
            df_primeira_compra['Data_Primeira_Compra'].dt.to_period('M') == '2025-07'
        ]
        
        if layout_mode == "🖥️ Desktop":
            col1, col2, col3 = st.columns(3)
        else:
            col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Clientes Novos em Julho", len(clientes_julho_df))
        
        with col2:
            if not vendas_julho.empty:
                media_julho = vendas_julho['Total_Venda'].mean()
                st.metric("Média Primeira Compra", f"R$ {media_julho:,.2f}")
        
        if layout_mode == "🖥️ Desktop":
            with col3:
                if not vendas_julho.empty:
                    total_julho = vendas_julho['Total_Venda'].sum()
                    st.metric("Total Faturado (1ª Compra)", f"R$ {total_julho:,.2f}")
        else:
            # Para mobile, colocar em uma nova linha
            if not vendas_julho.empty:
                total_julho = vendas_julho['Total_Venda'].sum()
                st.metric("Total Faturado (1ª Compra)", f"R$ {total_julho:,.2f}")
        
        # Lista de clientes novos em Julho
        st.subheader("📋 Lista de Clientes Novos em Julho")
        
        if not vendas_julho.empty:
            julho_detalhado = vendas_julho[['Nome_Cliente', 'Data_Primeira_Compra', 'Total_Venda']].copy()
            julho_detalhado['Data_Primeira_Compra'] = julho_detalhado['Data_Primeira_Compra'].dt.strftime('%d/%m/%Y')
            julho_detalhado = julho_detalhado.sort_values('Total_Venda', ascending=False)
            
            st.dataframe(
                julho_detalhado,
                column_config={
                    'Nome_Cliente': 'Cliente',
                    'Data_Primeira_Compra': 'Data da 1ª Compra',
                    'Total_Venda': st.column_config.NumberColumn(
                        'Valor 1ª Compra (R$)',
                        format="R$ %.2f"
                    )
                },
                use_container_width=True,
                hide_index=True
            )
        

    
    else:
        st.info("Nenhum cliente novo encontrado em Julho de 2025.")
    
    # Lista completa de clientes novos por mês COM VALORES
    st.markdown("---")
    st.subheader("📝 Lista Completa de Clientes Novos por Mês")
    
    # Criar dados mais detalhados para a lista
    for mes_periodo in primeira_compra['Mes_Primeira_Compra'].unique():
        if pd.isna(mes_periodo):
            continue
            
        # Clientes do mês
        clientes_mes = primeira_compra[primeira_compra['Mes_Primeira_Compra'] == mes_periodo]
        vendas_mes = df_primeira_compra[df_primeira_compra['Data_Primeira_Compra'].dt.to_period('M') == mes_periodo]
        
        # Nome do mês
        try:
            mes_nome = pd.to_datetime(str(mes_periodo)).strftime('%B de %Y')
        except:
            mes_nome = str(mes_periodo)
        
        with st.expander(f"📅 {mes_nome} - {len(clientes_mes)} clientes novos"):
            if not vendas_mes.empty:
                # Merge para obter os valores
                clientes_com_valores = vendas_mes[['Nome_Cliente', 'Total_Venda']].sort_values('Total_Venda', ascending=False)
                
                for i, (_, row) in enumerate(clientes_com_valores.iterrows(), 1):
                    cliente = row['Nome_Cliente']
                    valor = row['Total_Venda']
                    st.write(f"**{i}. {cliente}** - R$ {valor:,.2f} (primeira compra)")
            else:
                # Fallback caso não tenha valores
                for i, cliente in enumerate(clientes_mes['Nome_Cliente'].tolist(), 1):
                    st.write(f"{i}. {cliente}")

def analise_reativacao_clientes(df, layout_mode):
    """Análise de oportunidades de reativação"""
    st.title("🎯 Análise de Reativação - Grãos S.A.")
    st.markdown("*Identifique oportunidades de recuperar clientes e calcule o potencial financeiro*")
    
    # Preparando dados para análise de reativação
    clientes_resumo = df.groupby('Nome_Cliente').agg({
        'Total_Venda': ['sum', 'count', 'mean'],
        'Data_Competencia': ['min', 'max']
    }).reset_index()
    
    clientes_resumo.columns = ['Nome_Cliente', 'Total_Faturamento', 'Quantidade_Compras', 'Ticket_Medio', 'Primeira_Compra', 'Ultima_Compra']
    
    # Calculando recência
    data_atual = df['Data_Competencia'].max()
    clientes_resumo['Dias_Ultima_Compra'] = (data_atual - clientes_resumo['Ultima_Compra']).dt.days
    
    # 1. CLIENTES QUE COMPRARAM SÓ UMA VEZ (excluindo novos)
    clientes_uma_compra = clientes_resumo[
        (clientes_resumo['Quantidade_Compras'] == 1) & 
        (clientes_resumo['Dias_Ultima_Compra'] > 30)
    ].copy()
    
    # 2. CLIENTES INATIVOS (padrão: mais de 60 dias sem comprar)
    clientes_inativos = clientes_resumo[
        (clientes_resumo['Quantidade_Compras'] > 1) & 
        (clientes_resumo['Dias_Ultima_Compra'] > 60)
    ].copy()
    
    # Métricas principais
    if layout_mode == "🖥️ Desktop":
        col1, col2, col3, col4 = st.columns(4)
    else:
        col1, col2 = st.columns(2)
    
    with col1:
        qtd_uma_compra = len(clientes_uma_compra)
        st.metric(
            "Clientes com 1 Compra Apenas", 
            qtd_uma_compra,
            help="Clientes que compraram apenas uma vez há mais de 30 dias"
        )
    
    with col2:
        potencial_uma_compra = clientes_uma_compra['Total_Faturamento'].sum()
        st.metric(
            "💰 Potencial de Reativação", 
            f"R$ {potencial_uma_compra:,.2f}",
            help="Dinheiro que pode voltar se reativarmos clientes de 1 compra"
        )
    
    if layout_mode == "🖥️ Desktop":
        with col3:
            qtd_inativos = len(clientes_inativos)
            st.metric(
                "Clientes Inativos (60+ dias)", 
                qtd_inativos,
                help="Clientes que compraram mais de uma vez mas estão inativos há 60+ dias"
            )
        
        with col4:
            potencial_inativos = clientes_inativos['Total_Faturamento'].sum()
            st.metric(
                "💸 Faturamento Perdido", 
                f"R$ {potencial_inativos:,.2f}",
                help="Faturamento histórico dos clientes que estão inativos"
            )
    else:
        # Mobile - segunda linha
        col3, col4 = st.columns(2)
        with col3:
            qtd_inativos = len(clientes_inativos)
            st.metric(
                "Clientes Inativos (60+ dias)", 
                qtd_inativos,
                help="Clientes que compraram mais de uma vez mas estão inativos há 60+ dias"
            )
        
        with col4:
            potencial_inativos = clientes_inativos['Total_Faturamento'].sum()
            st.metric(
                "💸 Faturamento Perdido", 
                f"R$ {potencial_inativos:,.2f}",
                help="Faturamento histórico dos clientes que estão inativos"
            )
    
    st.markdown("---")
    
    # Análise detalhada em tabs
    tab1, tab2, tab3 = st.tabs([
        "🔄 Clientes de 1 Compra", 
        "😴 Clientes Inativos", 
        "📊 Resumo Executivo"
    ])
    
    with tab1:
        st.subheader("🎯 Clientes que Compraram Apenas Uma Vez")
        st.markdown("*Oportunidade de segunda compra - exclui clientes novos (últimos 30 dias)*")
        
        if not clientes_uma_compra.empty:
            # Ordenar por valor para priorizar
            clientes_uma_compra_sorted = clientes_uma_compra.sort_values('Total_Faturamento', ascending=False)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                ticket_medio_uma = clientes_uma_compra['Total_Faturamento'].mean()
                st.metric("Ticket Médio desta Categoria", f"R$ {ticket_medio_uma:,.2f}")
            
            with col2:
                dias_medio_inativo = clientes_uma_compra['Dias_Ultima_Compra'].mean()
                st.metric("Tempo Médio sem Comprar", f"{dias_medio_inativo:.0f} dias")
            
            with col3:
                # Estimativa conservadora: 20% de taxa de reativação
                estimativa_reativacao = potencial_uma_compra * 0.2
                st.metric("Estimativa Conservadora (20%)", f"R$ {estimativa_reativacao:,.2f}")
            
            st.markdown("**📋 Lista de Clientes Prioritários:**")
            st.dataframe(
                clientes_uma_compra_sorted.head(20)[['Nome_Cliente', 'Total_Faturamento', 'Dias_Ultima_Compra', 'Primeira_Compra']],
                column_config={
                    'Nome_Cliente': 'Cliente',
                    'Total_Faturamento': st.column_config.NumberColumn('Valor da Única Compra', format="R$ %.2f"),
                    'Dias_Ultima_Compra': 'Dias sem Comprar',
                    'Primeira_Compra': st.column_config.DateColumn('Data da Compra')
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Nenhum cliente encontrado nesta categoria.")
    
    with tab2:
        st.subheader("😴 Clientes Inativos (Padrão: 60+ dias)")
        st.markdown("*Clientes com histórico de compras que pararam de comprar*")
        
        if not clientes_inativos.empty:
            clientes_inativos_sorted = clientes_inativos.sort_values('Total_Faturamento', ascending=False)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                ticket_medio_inativo = clientes_inativos['Ticket_Medio'].mean()
                st.metric("Ticket Médio Histórico", f"R$ {ticket_medio_inativo:,.2f}")
            
            with col2:
                dias_medio_inativo = clientes_inativos['Dias_Ultima_Compra'].mean()
                st.metric("Tempo Médio sem Comprar", f"{dias_medio_inativo:.0f} dias")
            
            with col3:
                # Estimativa: 15% de taxa de reativação para inativos
                estimativa_inativos = clientes_inativos['Ticket_Medio'].sum() * 0.15
                st.metric("Potencial de Recuperação (15%)", f"R$ {estimativa_inativos:,.2f}")
            
            st.markdown("**📋 Clientes de Alto Valor Inativos:**")
            st.dataframe(
                clientes_inativos_sorted.head(20)[['Nome_Cliente', 'Total_Faturamento', 'Quantidade_Compras', 'Ticket_Medio', 'Dias_Ultima_Compra']],
                column_config={
                    'Nome_Cliente': 'Cliente',
                    'Total_Faturamento': st.column_config.NumberColumn('Faturamento Total', format="R$ %.2f"),
                    'Quantidade_Compras': 'Nº Compras',
                    'Ticket_Medio': st.column_config.NumberColumn('Ticket Médio', format="R$ %.2f"),
                    'Dias_Ultima_Compra': 'Dias sem Comprar'
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Nenhum cliente inativo encontrado.")
    
    with tab3:
        st.subheader("📊 Resumo Executivo - Oportunidades de Reativação")
        
        # Calculando totais
        total_oportunidade = potencial_uma_compra + potencial_inativos
        estimativa_total = (potencial_uma_compra * 0.2) + (clientes_inativos['Ticket_Medio'].sum() * 0.15 if not clientes_inativos.empty else 0)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 💰 Potencial Financeiro Total")
            st.metric("Valor Total em Risco", f"R$ {total_oportunidade:,.2f}")
            st.metric("Estimativa Conservadora de Recuperação", f"R$ {estimativa_total:,.2f}")
            
            # Gráfico de potencial
            dados_potencial = {
                'Categoria': ['1 Compra Apenas', 'Clientes Inativos'],
                'Valor': [potencial_uma_compra, potencial_inativos],
                'Clientes': [len(clientes_uma_compra), len(clientes_inativos)]
            }
            
            fig_potencial = px.bar(
                dados_potencial,
                x='Categoria',
                y='Valor',
                title='Potencial Financeiro por Categoria',
                labels={'Valor': 'Valor (R$)'},
                text='Clientes'
            )
            fig_potencial.update_traces(texttemplate='%{text} clientes', textposition='outside')
            st.plotly_chart(fig_potencial, use_container_width=True)
        
        with col2:
            st.markdown("### 🎯 Recomendações Estratégicas")
            
            if len(clientes_uma_compra) > 0:
                st.success(f"**Foco em 1ª Compra:** {len(clientes_uma_compra)} clientes com potencial de R$ {potencial_uma_compra:,.2f}")
                st.markdown("- Campanha de segunda compra")
                st.markdown("- Oferta especial de retorno")
                st.markdown("- Pesquisa de satisfação")
            
            if len(clientes_inativos) > 0:
                st.warning(f"**Reativação Urgente:** {len(clientes_inativos)} clientes inativos representam R$ {potencial_inativos:,.2f}")
                st.markdown("- Campanha de win-back")
                st.markdown("- Desconto especial")
                st.markdown("- Contato direto personalizado")
            
            st.info("💡 **Dica:** Priorize clientes com maior valor histórico para maximizar ROI da campanha")

def tela_boas_vindas():
    """Tela de boas-vindas para novos usuários"""
    
    # Estilo para a tela de boas-vindas
    st.markdown("""
    <style>
    .welcome-container {
        background: linear-gradient(135deg, #2E7D32 0%, #4CAF50 100%);
        padding: 3rem;
        border-radius: 20px;
        margin: 2rem 0;
        text-align: center;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }
    .welcome-title {
        color: white;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .welcome-subtitle {
        color: #E8F5E8;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    .welcome-text {
        color: white;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Container principal de boas-vindas
    st.markdown("""
    <div class="welcome-container">
        <div class="welcome-title">🌾 Bem-vindo à Grãos S.A.</div>
        <div class="welcome-subtitle">Central de Análises de Clientes</div>
        <div class="welcome-text">
            Sistema completo para análise estratégica da sua base de clientes.<br>
            Identifique oportunidades, segmente clientes e maximize resultados.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Logo da empresa
    try:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image("LOGO NOVA LINES (3).png", width=300)
    except:
        pass  # Se não conseguir carregar a logo, continua sem ela
    
    st.markdown("### 🖥️ Escolha o Layout Ideal para sua Experiência")
    st.markdown("*Selecione o formato que melhor se adapta ao seu dispositivo:*")
    
    # Botões de seleção de layout
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        col_desktop, col_mobile = st.columns(2)
        
        with col_desktop:
            if st.button("🖥️ Desktop", use_container_width=True, help="Ideal para computadores e telas grandes"):
                st.session_state.layout_mode = "🖥️ Desktop"
                st.session_state.primeira_vez = False
                st.rerun()
        
        with col_mobile:
            if st.button("📱 Mobile", use_container_width=True, help="Otimizado para tablets e celulares"):
                st.session_state.layout_mode = "📱 Mobile"
                st.session_state.primeira_vez = False
                st.rerun()
    
    st.markdown("---")
    st.markdown("*💡 Você pode alterar o layout a qualquer momento usando os botões no header.*")

def main():
    """Função principal com navegação entre análises"""
    
    # Verificar se é a primeira vez do usuário
    if 'primeira_vez' not in st.session_state:
        st.session_state.primeira_vez = True
    
    # Se for primeira vez, mostrar tela de boas-vindas
    if st.session_state.primeira_vez:
        tela_boas_vindas()
        return
    
    # Header com navegação bonita
    st.markdown("""
    <style>
    .header-container {
        background: linear-gradient(90deg, #2E7D32 0%, #4CAF50 100%);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
    }
    .header-title {
        color: white;
        font-size: 2rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .header-subtitle {
        color: #E8F5E8;
        font-size: 1rem;
        margin-bottom: 1rem;
    }
    .nav-buttons {
        display: flex;
        justify-content: center;
        gap: 1rem;
        flex-wrap: wrap;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="header-container">
        <div class="header-title">🌾 Central de Análises de Clientes - Grãos S.A.</div>
        <div class="header-subtitle">Sistema Estratégico de Gestão de Clientes</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Navegação em colunas bonitas
    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1.5, 1.5])
    
    with col1:
        if st.button("👶 Clientes Novos", use_container_width=True, help="Análise de aquisição de novos clientes"):
            st.session_state.analise_selecionada = "novos"
    
    with col2:
        if st.button("👥 Análise Geral", use_container_width=True, help="Segmentação completa da base de clientes"):
            st.session_state.analise_selecionada = "geral"
    
    with col3:
        if st.button("🎯 Reativação", use_container_width=True, help="Oportunidades de recuperar clientes inativos"):
            st.session_state.analise_selecionada = "reativacao"
    
    with col4:
        if st.button("🖥️ Desktop", use_container_width=True, help="Layout para desktop", type="secondary"):
            st.session_state.layout_mode = "🖥️ Desktop"
    
    with col5:
        if st.button("📱 Mobile", use_container_width=True, help="Layout para mobile", type="secondary"):
            st.session_state.layout_mode = "📱 Mobile"
    
    # Inicializar sessão se não existir
    if 'analise_selecionada' not in st.session_state:
        st.session_state.analise_selecionada = "novos"
    
    # Layout já foi definido na tela de boas-vindas
    if 'layout_mode' not in st.session_state:
        st.session_state.layout_mode = "🖥️ Desktop"
    
    st.markdown("---")
    
    # Carregando dados uma vez só
    with st.spinner("Carregando dados..."):
        df = carregar_dados()
    
    if df.empty:
        st.error("Não foi possível carregar os dados!")
        return
    
    # Exibir análise selecionada
    if st.session_state.analise_selecionada == "novos":
        analise_clientes_novos(df, st.session_state.layout_mode)
    elif st.session_state.analise_selecionada == "geral":
        analise_geral_clientes(df, st.session_state.layout_mode)
    else:
        analise_reativacao_clientes(df, st.session_state.layout_mode)

if __name__ == "__main__":
    main()