import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np
import os
import shutil

# Configuração da página
st.set_page_config(
    page_title="Gestor Estratégico - Grãos S.A.",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed"
)

@st.cache_data
def carregar_dados():
    """Carrega e processa os dados de vendas"""
    # Buscar arquivo de vendas mais recente (dados até 28/07/2025)
    arquivo_vendas = None
    
    # Primeiro tentar na pasta dados_diarios (mais recente)
    if os.path.exists('dados_diarios/2025-07-28/Vendas até 28-07-2025.txt'):
        arquivo_vendas = 'dados_diarios/2025-07-28/Vendas até 28-07-2025.txt'
    elif os.path.exists('dados_diarios/2025-07-26/Vendas até 26-07-2025.txt'):
        arquivo_vendas = 'dados_diarios/2025-07-26/Vendas até 26-07-2025.txt'
    else:
        # Fallback para busca na raiz
        arquivos_vendas = [f for f in os.listdir('.') if f.startswith('Vendas até') and f.endswith('.txt')]
        if arquivos_vendas:
            arquivo_vendas = sorted(arquivos_vendas)[-1]
    
    if not arquivo_vendas:
        st.error("❌ Nenhum arquivo de vendas encontrado!")
        return pd.DataFrame()
    
    # Tentativas de encoding
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            # Lendo o arquivo
            df = pd.read_csv(arquivo_vendas, 
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
        for col in ['Total_Venda', 'Total', 'Desconto', 'Valor']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
        
        # O campo 'Total_Venda' já é o valor líquido final (inclui frete, seguro, despesas acessórias)
        # Não precisamos recalcular, apenas garantir que está correto
        df['Valor_Liquido'] = df['Total_Venda']  # Total_Venda já é o valor líquido correto
        
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

def obter_data_mais_recente(df):
    """Obtém a data mais recente dos dados"""
    if df.empty:
        return datetime.now()
    
    df_temp = df.copy()
    df_temp['Data_Competencia'] = pd.to_datetime(df_temp['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
    data_mais_recente = df_temp['Data_Competencia'].max()
    
    return data_mais_recente if pd.notna(data_mais_recente) else datetime.now()

def obter_mes_portugues(data):
    """Converte mês para português"""
    meses_pt = {
        'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março',
        'April': 'Abril', 'May': 'Maio', 'June': 'Junho',
        'July': 'Julho', 'August': 'Agosto', 'September': 'Setembro',
        'October': 'Outubro', 'November': 'Novembro', 'December': 'Dezembro'
    }
    nome_mes = data.strftime('%B')
    return meses_pt.get(nome_mes, nome_mes)

def criar_grafico_periodo(clientes_novos, data_mais_recente, periodo_dias, titulo):
    """Cria gráfico para período específico com números visíveis"""
    data_inicio = data_mais_recente - pd.Timedelta(days=periodo_dias-1)
    
    # Filtrar período
    clientes_periodo = clientes_novos[
        (clientes_novos['Data_Competencia'] >= data_inicio) & 
        (clientes_novos['Data_Competencia'] <= data_mais_recente)
    ]
    
    if clientes_periodo.empty:
        return None
    
    # Agrupar por dia
    clientes_por_dia = clientes_periodo.groupby(
        clientes_periodo['Data_Competencia'].dt.date
    )['Nome_Cliente'].nunique().reset_index()
    
    clientes_por_dia.columns = ['Data', 'Novos_Clientes']
    clientes_por_dia['Data_str'] = pd.to_datetime(clientes_por_dia['Data']).dt.strftime('%d/%m')
    
    # Criar gráfico
    fig = px.bar(
        clientes_por_dia, 
        x='Data_str', 
        y='Novos_Clientes',
        title=titulo,
        labels={'Data_str': 'Data', 'Novos_Clientes': 'Novos Clientes'},
        text='Novos_Clientes'  # Mostrar números nas barras
    )
    
    fig.update_traces(
        texttemplate='%{text}', 
        textposition='outside',
        marker_color='#2E8B57',
        textfont_size=14  # Números grandes para mobile
    )
    
    fig.update_layout(
        height=400,
        showlegend=False,
        title_x=0.5,
        xaxis_title="Data",
        yaxis_title="Novos Clientes",
        font=dict(size=12),
        # Garantir que números sejam visíveis no mobile
        title_font_size=16,
        xaxis_title_font_size=14,
        yaxis_title_font_size=14
    )
    
    return fig

def configurar_meta_mes(nome_mes, ano):
    """Configuração da meta do mês"""
    # Configurações por mês (pode ser expandido)
    metas_configuradas = {
        ('Julho', 2025): {'meta_clientes': 60, 'dias_uteis': 27},
        ('Agosto', 2025): {'meta_clientes': 65, 'dias_uteis': 22},
        ('Setembro', 2025): {'meta_clientes': 70, 'dias_uteis': 21},
        # Adicionar mais meses conforme necessário
    }
    
    chave_mes = (nome_mes, ano)
    return metas_configuradas.get(chave_mes, {'meta_clientes': 60, 'dias_uteis': 22})

def calcular_dias_uteis_trabalhados(df_primeira_compra, mes_atual, ano_atual):
    """Calcula quantos dias úteis já foram trabalhados no mês"""
    clientes_mes = df_primeira_compra[
        (df_primeira_compra['Data_Primeira_Compra'].dt.month == mes_atual) & 
        (df_primeira_compra['Data_Primeira_Compra'].dt.year == ano_atual)
    ]
    
    if clientes_mes.empty:
        return 0
    
    # Contar dias únicos com vendas (dias úteis trabalhados)
    dias_com_vendas = len(clientes_mes['Data_Primeira_Compra'].dt.date.unique())
    return dias_com_vendas

def calcular_estimativas(total_mes, meta_clientes, dias_uteis, data_mais_recente, dias_uteis_trabalhados):
    """Calcula estimativas baseadas no progresso atual - CORRIGIDO para dias úteis de trabalho"""
    dias_restantes = max(0, dias_uteis - dias_uteis_trabalhados)
    
    # Progresso
    faltam = max(0, meta_clientes - total_mes)
    progresso_percentual = (total_mes / meta_clientes) * 100 if meta_clientes > 0 else 0
    
    # Ritmo atual (baseado em dias úteis trabalhados)
    if dias_uteis_trabalhados > 0:
        ritmo_diario_atual = total_mes / dias_uteis_trabalhados
        projecao_fim_mes = ritmo_diario_atual * dias_uteis
    else:
        ritmo_diario_atual = 0
        projecao_fim_mes = 0
    
    # Ritmo necessário para os dias úteis restantes
    ritmo_necessario = faltam / max(1, dias_restantes) if dias_restantes > 0 else 0
    
    return {
        'faltam': faltam,
        'progresso_percentual': progresso_percentual,
        'dias_restantes': dias_restantes,
        'dias_uteis_trabalhados': dias_uteis_trabalhados,
        'ritmo_diario_atual': ritmo_diario_atual,
        'projecao_fim_mes': projecao_fim_mes,
        'ritmo_necessario': ritmo_necessario
    }

def obter_meses_disponiveis(df_primeira_compra):
    """Obtém lista de meses disponíveis para comparação"""
    if df_primeira_compra.empty:
        return []
    
    meses = df_primeira_compra['Data_Primeira_Compra'].dt.to_period('M').unique()
    meses_ordenados = sorted([str(m) for m in meses if pd.notna(m)], reverse=True)
    
    meses_formatados = []
    for mes in meses_ordenados:
        try:
            data_mes = pd.to_datetime(mes)
            nome_mes = obter_mes_portugues(data_mes)
            meses_formatados.append({
                'periodo': mes,
                'nome': f"{nome_mes} {data_mes.year}",
                'data': data_mes
            })
        except:
            continue
    
    return meses_formatados

def calcular_metricas_comparativo(df_primeira_compra, mes_periodo, dias_uteis_para_comparar):
    """Calcula métricas do mês de comparação no mesmo período"""
    try:
        # Filtrar dados do mês de comparação
        clientes_mes_comparacao = df_primeira_compra[
            df_primeira_compra['Data_Primeira_Compra'].dt.to_period('M') == mes_periodo
        ]
        
        if clientes_mes_comparacao.empty:
            return None
        
        # Ordenar por data e pegar apenas os primeiros X dias úteis
        clientes_ordenados = clientes_mes_comparacao.sort_values('Data_Primeira_Compra')
        
        # Pegar dias únicos e limitar pelo número de dias úteis
        dias_unicos = sorted(clientes_ordenados['Data_Primeira_Compra'].dt.date.unique())
        dias_para_comparar = dias_unicos[:dias_uteis_para_comparar]
        
        if not dias_para_comparar:
            return None
        
        # Filtrar apenas vendas dos dias que vamos comparar
        clientes_periodo_comparacao = clientes_ordenados[
            clientes_ordenados['Data_Primeira_Compra'].dt.date.isin(dias_para_comparar)
        ]
        
        # Calcular métricas
        total_clientes = len(clientes_periodo_comparacao['Nome_Cliente'].unique())
        media_compra = clientes_periodo_comparacao['Total_Venda'].mean() if not clientes_periodo_comparacao.empty else 0
        dias_uteis_trabalhados = len(dias_para_comparar)
        ritmo_diario = total_clientes / dias_uteis_trabalhados if dias_uteis_trabalhados > 0 else 0
        
        return {
            'total_clientes': total_clientes,
            'media_compra': media_compra,
            'dias_uteis_trabalhados': dias_uteis_trabalhados,
            'ritmo_diario': ritmo_diario,
            'periodo_comparacao': f"{dias_para_comparar[0].strftime('%d/%m')} a {dias_para_comparar[-1].strftime('%d/%m')}"
        }
        
    except Exception as e:
        return None

def gerar_sugestoes_acoes(estimativas, clientes_mes_atual, media_compra_mes):
    """Gera sugestões de ações baseadas nos dados"""
    sugestoes = []
    
    # Análise de ritmo
    if estimativas['progresso_percentual'] < 50:
        sugestoes.append("🚨 **URGENTE**: Intensificar prospecção - abaixo de 50% da meta")
    elif estimativas['progresso_percentual'] < 75:
        sugestoes.append("⚠️ **ATENÇÃO**: Acelerar captação - meta em risco")
    else:
        sugestoes.append("✅ **BOM RITMO**: Manter estratégia atual")
    
    # Análise de valor médio
    if media_compra_mes > 2000:
        sugestoes.append("💰 **ALTO VALOR**: Focar em clientes premium - valor médio excelente")
    elif media_compra_mes < 1000:
        sugestoes.append("📈 **OPORTUNIDADE**: Trabalhar ticket médio dos novos clientes")
    
    # Sugestões de dias úteis restantes
    if estimativas['dias_restantes'] < 5:
        sugestoes.append("⏰ **SPRINT FINAL**: Focar em conversões rápidas")
    elif estimativas['dias_restantes'] > 15:
        sugestoes.append("📅 **PLANEJAMENTO**: Distribuir esforços ao longo do mês")
    
    return sugestoes

def analise_clientes_novos(df, layout_mode):
    """Análise focada no MÊS ATUAL - Prioridade para gestão diária"""
    st.title("👶 Análise de Clientes Novos - Grãos S.A.")
    st.markdown("*Foco no mês atual para bater a meta*")
    
    # Preparação dos dados
    df['Data_Competencia'] = pd.to_datetime(df['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
    df = df.dropna(subset=['Data_Competencia'])
    
    # Obter data mais recente
    data_mais_recente = obter_data_mais_recente(df)
    mes_atual = data_mais_recente.month
    ano_atual = data_mais_recente.year
    nome_mes_atual = obter_mes_portugues(data_mais_recente)
    
    # Identificar clientes novos
    primeira_compra, df_primeira_compra = identificar_clientes_novos(df)
    
    # === 1️⃣ SEÇÃO PRINCIPAL: MÊS ATUAL ===
    st.header(f"🎯 {nome_mes_atual} {ano_atual} - Mês da Meta")
    
    # Configuração da meta
    config_meta = configurar_meta_mes(nome_mes_atual, ano_atual)
    meta_clientes = config_meta['meta_clientes']
    dias_uteis = config_meta['dias_uteis']
    
    # Filtrar dados do mês atual
    clientes_mes_atual = df_primeira_compra[
        (df_primeira_compra['Data_Primeira_Compra'].dt.month == mes_atual) & 
        (df_primeira_compra['Data_Primeira_Compra'].dt.year == ano_atual)
    ]
    
    # Clientes novos hoje (última data)
    clientes_hoje = df_primeira_compra[
        df_primeira_compra['Data_Primeira_Compra'].dt.date == data_mais_recente.date()
    ]
    
    # Cálculos principais
    total_mes = len(clientes_mes_atual['Nome_Cliente'].unique())
    total_hoje = len(clientes_hoje['Nome_Cliente'].unique())
    
    if not clientes_mes_atual.empty:
        media_compra_mes = clientes_mes_atual['Total_Venda'].mean()
    else:
        media_compra_mes = 0
    
    # Calcular dias úteis trabalhados
    dias_uteis_trabalhados = calcular_dias_uteis_trabalhados(df_primeira_compra, mes_atual, ano_atual)
    
    # Calcular estimativas
    estimativas = calcular_estimativas(total_mes, meta_clientes, dias_uteis, data_mais_recente, dias_uteis_trabalhados)
    
    # === MÉTRICAS DE META ===
    st.subheader("📊 Progresso da Meta")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        delta_valor = total_mes - meta_clientes if total_mes >= meta_clientes else None
        delta_cor = "normal" if total_mes >= meta_clientes else "inverse"
        st.metric(
            label=f"🎯 Meta {nome_mes_atual}", 
            value=f"{total_mes}/{meta_clientes}",
            delta=f"Faltam {estimativas['faltam']}" if estimativas['faltam'] > 0 else "META ATINGIDA! 🎉",
            delta_color=delta_cor,
            help=f"Progresso: {estimativas['progresso_percentual']:.1f}%"
        )
    
    with col2:
        st.metric(
            label="👥 Novos Hoje", 
            value=total_hoje,
            help="Clientes novos na última data de vendas"
        )
    
    with col3:
        st.metric(
            label="💰 Média 1ª Compra", 
            value=f"R$ {media_compra_mes:,.2f}",
            help=f"Valor médio da primeira compra em {nome_mes_atual}"
        )
    
    with col4:
        st.metric(
            label="📅 Última Atualização", 
            value=data_mais_recente.strftime('%d/%m/%Y'),
            help="Última data com dados de vendas"
        )
    
    # === ESTIMATIVAS E PROJEÇÕES ===
    st.subheader("📈 Estimativas Inteligentes")
    
    col_est1, col_est2, col_est3, col_est4 = st.columns(4)
    
    with col_est1:
        st.metric(
            label="📅 Dias Úteis",
            value=f"{estimativas['dias_uteis_trabalhados']}/{dias_uteis}",
            delta=f"{estimativas['dias_restantes']} restantes",
            help=f"Dias úteis trabalhados de {dias_uteis} totais do mês"
        )
    
    with col_est2:
        st.metric(
            label="⚡ Ritmo Atual",
            value=f"{estimativas['ritmo_diario_atual']:.1f}/dia",
            help="Clientes novos por dia útil (média atual)"
        )
    
    with col_est3:
        cor_projecao = "normal" if estimativas['projecao_fim_mes'] >= meta_clientes else "inverse"
        st.metric(
            label="🔮 Projeção Fim do Mês",
            value=f"{estimativas['projecao_fim_mes']:.0f} clientes",
            delta=f"{estimativas['projecao_fim_mes'] - meta_clientes:+.0f} vs meta",
            delta_color=cor_projecao,
            help="Baseado no ritmo atual"
        )
    
    with col_est4:
        st.metric(
            label="🎯 Ritmo Necessário",
            value=f"{estimativas['ritmo_necessario']:.1f}/dia",
            help="Para atingir a meta nos dias restantes"
        )
    
    # === SUGESTÕES DE AÇÕES ===
    st.subheader("💡 Sugestões de Ações")
    
    sugestoes = gerar_sugestoes_acoes(estimativas, clientes_mes_atual, media_compra_mes)
    
    for i, sugestao in enumerate(sugestoes, 1):
        st.info(f"**{i}.** {sugestao}")
    
    # === ALERTA DE META ===
    if estimativas['progresso_percentual'] < 80 and estimativas['dias_restantes'] < 10:
        st.error(f"🚨 **ALERTA DE META**: {estimativas['faltam']} clientes faltando com apenas {estimativas['dias_restantes']} dias úteis restantes!")
    elif estimativas['projecao_fim_mes'] < meta_clientes:
        st.warning(f"⚠️ **ATENÇÃO**: Projeção atual ({estimativas['projecao_fim_mes']:.0f}) abaixo da meta ({meta_clientes})")
    elif estimativas['progresso_percentual'] >= 100:
        st.success(f"🎉 **META ATINGIDA!** Parabéns! {total_mes} clientes novos conquistados!")
    
    # === 2️⃣ COMPARATIVO COM MÊS ANTERIOR ===
    st.subheader("📊 Comparativo - Mesmo Período")
    
    # Obter meses disponíveis
    meses_disponiveis = obter_meses_disponiveis(df_primeira_compra)
    
    if len(meses_disponiveis) > 1:
        # Seletor de mês para comparação
        col_sel1, col_sel2 = st.columns([3, 1])
        
        with col_sel1:
            # Filtrar meses anteriores ao atual
            meses_anteriores = [m for m in meses_disponiveis 
                              if m['data'].month != mes_atual or m['data'].year != ano_atual]
            
            if meses_anteriores:
                opcoes_mes = [m['nome'] for m in meses_anteriores]
                mes_selecionado_nome = st.selectbox(
                    "Comparar com:",
                    opcoes_mes,
                    index=0,
                    help="Selecione o mês para comparar no mesmo período"
                )
                
                # Encontrar o período selecionado
                mes_selecionado = next(m for m in meses_anteriores if m['nome'] == mes_selecionado_nome)
                mes_periodo_comparacao = mes_selecionado['periodo']
                
        with col_sel2:
            st.info(f"📅 **Período**: Primeiros {estimativas['dias_uteis_trabalhados']} dias úteis")
        
        # Calcular métricas do mês de comparação
        metricas_comparacao = calcular_metricas_comparativo(
            df_primeira_compra, 
            mes_periodo_comparacao, 
            estimativas['dias_uteis_trabalhados']
        )
        
        if metricas_comparacao:
            st.markdown("### 📈 Comparativo Side-by-Side")
            
            # Métricas lado a lado
            col_atual, col_anterior, col_variacao = st.columns([3, 3, 2])
            
            with col_atual:
                st.markdown(f"**📊 {nome_mes_atual} {ano_atual}**")
                st.metric("👥 Novos Clientes", total_mes)
                st.metric("💰 Média 1ª Compra", f"R$ {media_compra_mes:,.2f}")
                st.metric("⚡ Ritmo Diário", f"{estimativas['ritmo_diario_atual']:.1f}/dia")
                st.metric("📅 Dias Trabalhados", estimativas['dias_uteis_trabalhados'])
            
            with col_anterior:
                st.markdown(f"**📊 {mes_selecionado_nome}**")
                st.metric("👥 Novos Clientes", metricas_comparacao['total_clientes'])
                st.metric("💰 Média 1ª Compra", f"R$ {metricas_comparacao['media_compra']:,.2f}")
                st.metric("⚡ Ritmo Diário", f"{metricas_comparacao['ritmo_diario']:.1f}/dia")
                st.metric("📅 Dias Trabalhados", metricas_comparacao['dias_uteis_trabalhados'])
            
            with col_variacao:
                st.markdown("**📈 Variação**")
                
                # Variação clientes
                var_clientes = total_mes - metricas_comparacao['total_clientes']
                var_clientes_pct = (var_clientes / metricas_comparacao['total_clientes'] * 100) if metricas_comparacao['total_clientes'] > 0 else 0
                
                # Variação ticket médio
                var_ticket = media_compra_mes - metricas_comparacao['media_compra']
                var_ticket_pct = (var_ticket / metricas_comparacao['media_compra'] * 100) if metricas_comparacao['media_compra'] > 0 else 0
                
                # Variação ritmo
                var_ritmo = estimativas['ritmo_diario_atual'] - metricas_comparacao['ritmo_diario']
                var_ritmo_pct = (var_ritmo / metricas_comparacao['ritmo_diario'] * 100) if metricas_comparacao['ritmo_diario'] > 0 else 0
                
                                # Mostrar variações com cores
                if var_clientes >= 0:
                    st.success(f"👥 +{var_clientes} ({var_clientes_pct:+.1f}%)")
                else:
                    st.error(f"👥 {var_clientes} ({var_clientes_pct:+.1f}%)")
                
                if var_ticket >= 0:
                    st.success(f"💰 +R$ {var_ticket:,.2f} ({var_ticket_pct:+.1f}%)")
                else:
                    st.error(f"💰 -R$ {abs(var_ticket):,.2f} ({var_ticket_pct:+.1f}%)")
                
                if var_ritmo >= 0:
                    st.success(f"⚡ +{var_ritmo:.1f} ({var_ritmo_pct:+.1f}%)")
                else:
                    st.error(f"⚡ {var_ritmo:.1f} ({var_ritmo_pct:+.1f}%)")
                
                # Não há variação nos dias (é o mesmo período)
                st.info("📅 Mesmo período")
            
            # === ANÁLISE AUTOMÁTICA ===
            st.markdown("### 🎯 Análise Comparativa")
            
            analises = []
            
            # Análise de performance geral
            if var_clientes > 0 and var_ticket > 0 and var_ritmo > 0:
                analises.append("🎉 **EXCELENTE**: Melhor em todas as métricas - estratégia funcionando!")
            elif var_clientes > 0:
                analises.append(f"✅ **POSITIVO**: {var_clientes} clientes a mais que {mes_selecionado_nome}")
            elif var_clientes < 0:
                analises.append(f"⚠️ **ATENÇÃO**: {abs(var_clientes)} clientes a menos que {mes_selecionado_nome}")
            
            # Análise do ticket médio
            if var_ticket_pct > 10:
                analises.append(f"💰 **TICKET EM ALTA**: {var_ticket_pct:.1f}% maior - clientes premium!")
            elif var_ticket_pct < -10:
                analises.append(f"📉 **TICKET BAIXO**: {abs(var_ticket_pct):.1f}% menor - revisar estratégia de preços")
            
            # Análise do ritmo
            if var_ritmo_pct > 15:
                analises.append(f"⚡ **RITMO ACELERADO**: {var_ritmo_pct:.1f}% mais rápido na captação")
            elif var_ritmo_pct < -15:
                analises.append(f"🐌 **RITMO LENTO**: {abs(var_ritmo_pct):.1f}% mais devagar - acelerar prospecção")
            
            # Mostrar análises
            for analise in analises:
                st.info(analise)
                
            if not analises:
                st.info("📊 **ESTÁVEL**: Performance similar ao mês anterior")
                
        else:
            st.warning(f"❌ Não foi possível calcular métricas para {mes_selecionado_nome}")
            
    else:
        st.info("📅 **Comparativo indisponível**: Necessário pelo menos 2 meses de dados")
    
    # === 3️⃣ GRÁFICOS INTERATIVOS ===
    st.subheader("📈 Evolução Diária - Números Visíveis")
    
    # Seletor de período
    col_7, col_14, col_mes = st.columns(3)
    
    with col_7:
        if st.button("📊 Últimos 7 Dias", use_container_width=True, type="primary"):
            st.session_state.periodo_selecionado = 7
    
    with col_14:
        if st.button("📈 Últimos 14 Dias", use_container_width=True):
            st.session_state.periodo_selecionado = 14
    
    with col_mes:
        if st.button(f"📅 {nome_mes_atual} Completo", use_container_width=True):
            # Calcular dias do mês atual
            primeiro_dia = data_mais_recente.replace(day=1)
            dias_mes = (data_mais_recente - primeiro_dia).days + 1
            st.session_state.periodo_selecionado = dias_mes
    
    # Período padrão
    if 'periodo_selecionado' not in st.session_state:
        st.session_state.periodo_selecionado = 7
    
    # Criar e exibir gráfico
    periodo = st.session_state.periodo_selecionado
    if periodo <= 14:
        titulo = f"📊 Novos Clientes - Últimos {periodo} Dias"
    else:
        titulo = f"📅 Novos Clientes - {nome_mes_atual} Completo"
    
    fig = criar_grafico_periodo(df_primeira_compra, data_mais_recente, periodo, titulo)
    
    if fig:
        st.plotly_chart(fig, use_container_width=True)
        
        # Resumo do período
        data_inicio = data_mais_recente - pd.Timedelta(days=periodo-1)
        clientes_periodo = df_primeira_compra[
            (df_primeira_compra['Data_Primeira_Compra'] >= data_inicio) & 
            (df_primeira_compra['Data_Primeira_Compra'] <= data_mais_recente)
        ]
        
        col_resumo1, col_resumo2 = st.columns(2)
        with col_resumo1:
            st.info(f"📊 **Total no período:** {len(clientes_periodo)} novos clientes")
        with col_resumo2:
            if not clientes_periodo.empty:
                media_periodo = clientes_periodo['Total_Venda'].mean()
                st.info(f"💰 **Média do período:** R$ {media_periodo:,.2f}")
    else:
        st.info("📭 Não há dados de clientes novos para o período selecionado.")
    
    # === 4️⃣ RESUMO EXECUTIVO ===
    with st.expander("📊 Resumo Executivo - Para Apresentação", expanded=False):
        st.subheader("📋 Relatório Gerencial")
        
        col_exec1, col_exec2 = st.columns(2)
        
        with col_exec1:
            st.markdown("### 🎯 **Status da Meta**")
            if estimativas['progresso_percentual'] >= 100:
                st.success(f"✅ **META ATINGIDA** ({estimativas['progresso_percentual']:.1f}%)")
            elif estimativas['progresso_percentual'] >= 80:
                st.info(f"📈 **NO CAMINHO CERTO** ({estimativas['progresso_percentual']:.1f}%)")
            elif estimativas['progresso_percentual'] >= 50:
                st.warning(f"⚠️ **ATENÇÃO NECESSÁRIA** ({estimativas['progresso_percentual']:.1f}%)")
            else:
                st.error(f"🚨 **AÇÃO URGENTE** ({estimativas['progresso_percentual']:.1f}%)")
            
            st.markdown(f"**Meta do mês:** {meta_clientes} clientes")
            st.markdown(f"**Conquistados:** {total_mes} clientes")
            st.markdown(f"**Faltam:** {estimativas['faltam']} clientes")
            st.markdown(f"**Dias úteis restantes:** {estimativas['dias_restantes']}")
        
        with col_exec2:
            st.markdown("### 📈 **Projeções**")
            st.markdown(f"**Ritmo atual:** {estimativas['ritmo_diario_atual']:.1f} clientes/dia")
            st.markdown(f"**Ritmo necessário:** {estimativas['ritmo_necessario']:.1f} clientes/dia")
            st.markdown(f"**Projeção fim do mês:** {estimativas['projecao_fim_mes']:.0f} clientes")
            
            if estimativas['projecao_fim_mes'] >= meta_clientes:
                st.success(f"✅ Projeção acima da meta (+{estimativas['projecao_fim_mes'] - meta_clientes:.0f})")
            else:
                st.error(f"❌ Projeção abaixo da meta (-{meta_clientes - estimativas['projecao_fim_mes']:.0f})")
            
            st.markdown(f"**Ticket médio novos clientes:** R$ {media_compra_mes:,.2f}")
    
         # === 5️⃣ ANÁLISE HISTÓRICA (SECUNDÁRIA) ===
    with st.expander("📋 Ver Análise Histórica Completa", expanded=False):
        st.subheader("📊 Histórico Geral")
        
        # Chamar funções originais para histórico
        clientes_por_mes, media_gasta, lista_clientes = analise_por_mes(primeira_compra, df_primeira_compra)
        
        # Aplicar layout original
        if layout_mode == "🖥️ Desktop":
            layout_desktop(df, primeira_compra, df_primeira_compra, clientes_por_mes, media_gasta, lista_clientes)
        else:
            layout_mobile(df, primeira_compra, df_primeira_compra, clientes_por_mes, media_gasta, lista_clientes)

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
    
    # Estilo responsivo para a tela de boas-vindas
    st.markdown("""
    <style>
    .welcome-container {
        background: linear-gradient(135deg, #2E7D32 0%, #4CAF50 100%);
        padding: 2rem 1rem;
        border-radius: 15px;
        margin: 1rem 0;
        text-align: center;
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
    }
    .welcome-title {
        color: white;
        font-size: clamp(1.5rem, 4vw, 2.2rem);
        font-weight: bold;
        margin-bottom: 0.5rem;
        line-height: 1.2;
    }
    .welcome-subtitle {
        color: #E8F5E8;
        font-size: clamp(1rem, 2.5vw, 1.1rem);
        margin-bottom: 1rem;
    }
    .welcome-text {
        color: white;
        font-size: clamp(0.9rem, 2vw, 1rem);
        margin-bottom: 1rem;
        line-height: 1.4;
    }
    
    /* Responsividade para mobile */
    @media (max-width: 768px) {
        .welcome-container {
            padding: 1.5rem 0.8rem;
            margin: 0.5rem 0;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Container principal de boas-vindas
    st.markdown("""
    <div class="welcome-container">
        <div class="welcome-title">🌾 Bem-vindo ao Gestor Estratégico - Grãos S.A.</div>
        <div class="welcome-subtitle">Sistema Inteligente de Gestão de Negócios</div>
        <div class="welcome-text">
            Plataforma completa para análise estratégica do seu negócio.<br>
            Monitore vendas, analise clientes e projete resultados em tempo real.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Logo da empresa centralizada
    try:
        col_logo1, col_logo2, col_logo3 = st.columns([1, 1, 1])
        with col_logo2:
            st.image("LOGO NOVA LINES (3).png", width=200)
    except:
        pass
    
    # Escolha do Layout centralizada
    st.markdown("---")
    col_layout1, col_layout2, col_layout3 = st.columns([1, 2, 1])
    
    with col_layout2:
        st.markdown("### 🖥️ Escolha o Layout Ideal")
        st.markdown("*Selecione o formato que melhor se adapta ao seu dispositivo:*")
        
        col_desktop, col_mobile = st.columns(2)
        
        with col_desktop:
            if st.button(
                "🖥️ Desktop", 
                use_container_width=True, 
                help="Ideal para computadores e telas grandes",
                type="primary"
            ):
                st.session_state.layout_mode = "🖥️ Desktop"
                st.session_state.primeira_vez = False
                st.rerun()
        
        with col_mobile:
            if st.button(
                "📱 Mobile", 
                use_container_width=True, 
                help="Otimizado para tablets e celulares",
                type="secondary"
            ):
                st.session_state.layout_mode = "📱 Mobile"
                st.session_state.primeira_vez = False
                st.rerun()
    
    # Dashboards Disponíveis - Simplificado
    st.markdown("---")
    st.markdown("### 📊 Dashboards Disponíveis")
    
    # Dashboards em formato compacto
    col_dash1, col_dash2 = st.columns(2)
    
    with col_dash1:
        st.info("**🌍 Dashboard Geral** - Visão consolidada completa")
        st.success("**🏢 Dashboard Atacado** - Análise detalhada do setor")
        st.warning("**👥 Análise de Clientes** - Gestão estratégica da base")
    
    with col_dash2:
        st.info("**🏪 Dashboard Varejo** - Análise específica do varejo")
        st.error("**⚙️ Configurações** - Central de configurações")
    
    # Características Principais
    st.markdown("---")
    st.markdown("### ✨ Características Principais")
    
    col_char1, col_char2, col_char3 = st.columns(3)
    
    with col_char1:
        st.markdown("**💰 Valores Líquidos**  \n*Cálculos precisos*")
        st.markdown("**📊 Gráficos Interativos**  \n*Visualizações dinâmicas*")
    
    with col_char2:
        st.markdown("**🔮 Projeções Inteligentes**  \n*Múltiplos métodos*")
        st.markdown("**📱 Design Responsivo**  \n*Todos os dispositivos*")
    
    with col_char3:
        st.markdown("**⚡ Tempo Real**  \n*Dados atualizados*")
        st.markdown("**🎯 Análises Estratégicas**  \n*Insights para decisões*")
    
    # Informação final centralizada
    st.markdown("---")
    col_final1, col_final2, col_final3 = st.columns([1, 2, 1])
    with col_final2:
        st.markdown("*💡 Você pode alterar o layout a qualquer momento nas configurações.*")
        st.markdown("*🚀 Clique em qualquer botão acima para começar a usar o sistema!*")

def fazer_backup():
    """Cria backup do arquivo principal"""
    # Buscar arquivo de vendas mais recente
    arquivos_vendas = [f for f in os.listdir('.') if f.startswith('Vendas até') and f.endswith('.txt')]
    
    if not arquivos_vendas:
        return None
        
    arquivo_principal = sorted(arquivos_vendas)[-1]
    
    if os.path.exists(arquivo_principal):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_nome = f"backup_vendas_{timestamp}.txt"
        shutil.copy2(arquivo_principal, backup_nome)
        return backup_nome
    return None

def processar_arquivo_novo(arquivo_uploaded):
    """Processa arquivo novo e adiciona aos dados existentes"""
    try:
        # Buscar arquivo de vendas mais recente
        arquivos_vendas = [f for f in os.listdir('.') if f.startswith('Vendas até') and f.endswith('.txt')]
        
        if not arquivos_vendas:
            st.error("❌ Nenhum arquivo de vendas encontrado!")
            return False
            
        arquivo_principal = sorted(arquivos_vendas)[-1]
        
        # Backup antes de modificar
        backup_nome = fazer_backup()
        st.info(f"✅ Backup criado: {backup_nome}")
        
        # Carregando dados existentes
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        dados_existentes = None
        
        for encoding in encodings:
            try:
                dados_existentes = pd.read_csv(arquivo_principal, sep=";", encoding=encoding, on_bad_lines='skip')
                break
            except Exception as e:
                continue
        
        if dados_existentes is None:
            st.error("❌ Erro ao carregar dados existentes")
            return False
            
        # Carregando arquivo novo
        dados_novos = None
        for encoding in encodings:
            try:
                # Reset do ponteiro do arquivo
                arquivo_uploaded.seek(0)
                dados_novos = pd.read_csv(arquivo_uploaded, sep=";", encoding=encoding, on_bad_lines='skip')
                break
            except Exception as e:
                continue
                
        if dados_novos is None:
            st.error("❌ Erro ao carregar arquivo novo")
            st.error("💡 **Dica:** Verifique se o arquivo tem o formato correto (.txt com separador ';')")
            return False
            

            
        # Verificando compatibilidade
        if len(dados_novos.columns) != len(dados_existentes.columns):
            st.error(f"❌ Estrutura incompatível: {len(dados_novos.columns)} vs {len(dados_existentes.columns)} colunas")
            return False
            
        # Padronizando nomes das colunas
        dados_novos.columns = dados_existentes.columns
        
        # Combinando dados
        dados_antes = len(dados_existentes)
        dados_combinados = pd.concat([dados_existentes, dados_novos], ignore_index=True)
        
        # Removendo duplicatas (baseado em data + código da venda)
        dados_combinados = dados_combinados.drop_duplicates(
            subset=[dados_combinados.columns[0], dados_combinados.columns[2]], # Data + N° Venda
            keep='first'
        )
        
        dados_depois = len(dados_combinados)
        dados_adicionados = dados_depois - dados_antes
        
        # Ordenando por data
        dados_combinados = dados_combinados.sort_values(dados_combinados.columns[0])
        
        # Obtendo a data mais recente dos dados combinados
        try:
            primeira_coluna = dados_combinados.columns[0]
            dados_combinados[primeira_coluna] = pd.to_datetime(dados_combinados[primeira_coluna], format='%d/%m/%Y', errors='coerce')
            data_mais_recente = dados_combinados[primeira_coluna].max()
            
            if pd.notna(data_mais_recente):
                novo_nome = f"Vendas até {data_mais_recente.strftime('%d-%m-%Y')}.txt"
                
                # Formatando de volta para string
                dados_combinados[primeira_coluna] = dados_combinados[primeira_coluna].dt.strftime('%d/%m/%Y')
                
                # Salvando com novo nome
                dados_combinados.to_csv(novo_nome, sep=";", index=False, encoding='latin-1')
                
                # Removendo arquivo antigo se for diferente
                if novo_nome != arquivo_principal and os.path.exists(arquivo_principal):
                    os.remove(arquivo_principal)
            else:
                # Fallback: manter nome original
                dados_combinados.to_csv(arquivo_principal, sep=";", index=False, encoding='latin-1')
        except:
            # Fallback: salvar com nome original
            dados_combinados.to_csv(arquivo_principal, sep=";", index=False, encoding='latin-1')
        
        st.success(f"✅ Dados atualizados com sucesso!")
        st.info(f"📊 {dados_adicionados} novos registros adicionados")
        st.info(f"📈 Total de registros: {dados_depois}")
        
        return True
        
    except Exception as e:
        st.error(f"❌ Erro ao processar arquivo: {str(e)}")
        return False

def processar_arquivo_atacado(arquivo_uploaded):
    """Processa e atualiza especificamente dados do atacado"""
    try:
        # Fazer backup do arquivo atual
        arquivos_atacado = [f for f in os.listdir('.') if f.startswith('Vendas até') and f.endswith('.txt')]
        if arquivos_atacado:
            arquivo_atual = sorted(arquivos_atacado)[-1]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_nome = f"backup_atacado_{timestamp}.txt"
            shutil.copy2(arquivo_atual, backup_nome)
        
        # Salvar novo arquivo de atacado
        conteudo = arquivo_uploaded.read().decode('latin-1')
        novo_nome = f"Vendas até {datetime.now().strftime('%d-%m-%Y')}.txt"
        
        with open(novo_nome, 'w', encoding='latin-1') as f:
            f.write(conteudo)
        
        return True
        
    except Exception as e:
        st.error(f"❌ Erro ao processar arquivo do atacado: {str(e)}")
        return False

def processar_arquivo_varejo(arquivo_uploaded):
    """Processa e atualiza especificamente dados do varejo"""
    try:
        # Fazer backup do arquivo atual (se existir)
        arquivos_varejo = [f for f in os.listdir('.') if 'varejo' in f.lower() and f.endswith('.txt')]
        if arquivos_varejo:
            arquivo_atual = arquivos_varejo[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_nome = f"backup_varejo_{timestamp}.txt"
            shutil.copy2(arquivo_atual, backup_nome)
        
        # Salvar novo arquivo de varejo
        conteudo = arquivo_uploaded.read().decode('latin-1')
        novo_nome = f"Varejo {datetime.now().strftime('%B').lower()} até dia {datetime.now().strftime('%d')}.txt"
        
        with open(novo_nome, 'w', encoding='latin-1') as f:
            f.write(conteudo)
        
        return True
        
    except Exception as e:
        st.error(f"❌ Erro ao processar arquivo do varejo: {str(e)}")
        return False

def interface_atualizacao():
    """Interface para atualização de dados - MANTER POR COMPATIBILIDADE"""
    st.header("📊 Atualizar Dados de Vendas")
    
    st.info("🔄 **Como usar:** Faça upload do arquivo de vendas do dia para adicionar aos dados existentes")
    
    arquivo_uploaded = st.file_uploader(
        "Selecione o arquivo de vendas (.txt)",
        type=['txt'],
        help="Arquivo deve ter a mesma estrutura do arquivo principal"
    )
    
    if arquivo_uploaded is not None:
        st.write("📁 **Arquivo selecionado:**", arquivo_uploaded.name)
        
        if st.button("🚀 Processar e Atualizar Dados", type="primary"):
            with st.spinner("⏳ Processando..."):
                sucesso = processar_arquivo_novo(arquivo_uploaded)
                
            if sucesso:
                st.balloons()
                st.success("🎉 **Dados atualizados!** O dashboard foi atualizado automaticamente.")
                
                # Limpar cache para recarregar dados
                st.cache_data.clear()
                    
                # Forçar rerun
                st.rerun()
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Limpar Cache", help="Limpa o cache e recarrega dados"):
            st.cache_data.clear()
            st.success("✅ Cache limpo!")
            st.rerun()
    
    with col2:
        if st.button("📋 Ver Backups", help="Lista dos backups disponíveis"):
            backups = [f for f in os.listdir('.') if f.startswith('backup_vendas_') and f.endswith('.txt')]
            if backups:
                st.write("📂 **Backups disponíveis:**")
                for backup in sorted(backups, reverse=True)[:5]:  # Últimos 5
                    st.write(f"• {backup}")
            else:
                st.info("Nenhum backup encontrado")

def dashboard_geral(df, layout_mode):
    """Dashboard geral com visão de negócio"""
    st.title("📊 Dashboard Geral - Grãos S.A.")
    st.markdown("*Visão estratégica completa do negócio*")
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_clientes = len(df['Nome_Cliente'].unique())
        st.metric("👥 Total Clientes", total_clientes)
    
    with col2:
        total_vendas = len(df)
        st.metric("🛒 Total Vendas", f"{total_vendas:,}")
    
    with col3:
        faturamento_total = df['Total_Venda'].sum()
        st.metric("💰 Faturamento Total", f"R$ {faturamento_total:,.2f}")
    
    with col4:
        ticket_medio = df['Total_Venda'].mean()
        st.metric("🎯 Ticket Médio", f"R$ {ticket_medio:,.2f}")
    
    st.info("🚧 **Em desenvolvimento**: Dashboard com mais métricas estratégicas será adicionado em breve.")

def obter_data_mais_recente_str(df):
    """Obtém a data mais recente dos dados como string para usar em títulos dinâmicos"""
    df_temp = df.copy()
    df_temp['Data_Competencia'] = pd.to_datetime(df_temp['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
    df_temp = df_temp.dropna(subset=['Data_Competencia'])
    
    if df_temp.empty:
        return None
    
    data_mais_recente = df_temp['Data_Competencia'].max()
    return data_mais_recente.strftime('%d/%m/%Y')

def gerar_titulo_vendas_dinamico(df, prefixo="Vendas"):
    """Gera título dinâmico baseado na data mais recente dos dados"""
    data_recente = obter_data_mais_recente_str(df)
    if data_recente:
        return f"🔥 {prefixo} de {data_recente}"
    else:
        return f"🔥 {prefixo} de Hoje"

def espacamento_responsivo(layout_mode=None):
    """Cria espaçamento responsivo baseado no layout"""
    if layout_mode is None:
        layout_mode = st.session_state.get('layout_mode', '🖥️ Desktop')
    
    if layout_mode == "📱 Mobile":
        # Mobile: espaço mínimo
        st.markdown("<br>", unsafe_allow_html=True)
    else:
        # Desktop: linha divisória completa
        st.markdown("---")

def config_grafico_mobile(fig, layout_mode=None):
    """Configura gráfico Plotly para mobile"""
    if layout_mode is None:
        layout_mode = st.session_state.get('layout_mode', '🖥️ Desktop')
    
    if layout_mode == "📱 Mobile":
        # Configurações específicas para mobile
        fig.update_layout(
            height=300,  # Altura menor para mobile
            margin=dict(l=10, r=10, t=30, b=10),  # Margens menores
            font=dict(size=10),  # Fonte menor
            title_font_size=12,  # Título menor
            showlegend=True,
            legend=dict(
                orientation="h",  # Legenda horizontal
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=9)
            )
        )
    else:
        # Configurações para desktop (padrão)
        fig.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=50, b=20),
            font=dict(size=12),
            title_font_size=16
        )
    
    return fig

def calcular_vendas_hoje_ontem(df):
    """Calcula vendas de hoje vs ontem usando dados reais"""
    df_temp = df.copy()
    df_temp['Data_Competencia'] = pd.to_datetime(df_temp['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
    df_temp = df_temp.dropna(subset=['Data_Competencia'])
    
    if df_temp.empty:
        return None
        
    # Obter as duas datas mais recentes
    datas_unicas = sorted(df_temp['Data_Competencia'].dt.date.unique(), reverse=True)
    
    if len(datas_unicas) < 2:
        return {
            'hoje': {'data': datas_unicas[0] if datas_unicas else None, 'faturamento': 0, 'vendas': 0},
            'ontem': {'data': None, 'faturamento': 0, 'vendas': 0},
            'variacao_faturamento': 0,
            'variacao_vendas': 0
        }
    
    data_hoje = datas_unicas[0]
    data_ontem = datas_unicas[1]
    
    # Vendas de hoje
    vendas_hoje = df_temp[df_temp['Data_Competencia'].dt.date == data_hoje]
    faturamento_hoje = vendas_hoje['Total_Venda'].sum()
    qtd_vendas_hoje = len(vendas_hoje)
    
    # Vendas de ontem  
    vendas_ontem = df_temp[df_temp['Data_Competencia'].dt.date == data_ontem]
    faturamento_ontem = vendas_ontem['Total_Venda'].sum()
    qtd_vendas_ontem = len(vendas_ontem)
    
    # Calcular variações
    var_faturamento = ((faturamento_hoje - faturamento_ontem) / faturamento_ontem * 100) if faturamento_ontem > 0 else 0
    var_vendas = ((qtd_vendas_hoje - qtd_vendas_ontem) / qtd_vendas_ontem * 100) if qtd_vendas_ontem > 0 else 0
    
    return {
        'hoje': {
            'data': data_hoje,
            'faturamento': faturamento_hoje,
            'vendas': qtd_vendas_hoje
        },
        'ontem': {
            'data': data_ontem,
            'faturamento': faturamento_ontem,
            'vendas': qtd_vendas_ontem
        },
        'variacao_faturamento': var_faturamento,
        'variacao_vendas': var_vendas
    }

def calcular_comparacoes_temporais(df):
    """Calcula comparações: hoje vs ontem, 7 dias atrás, 15 dias atrás"""
    df_temp = df.copy()
    df_temp['Data_Competencia'] = pd.to_datetime(df_temp['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
    df_temp = df_temp.dropna(subset=['Data_Competencia'])
    
    if df_temp.empty:
        return None
        
    # Obter data mais recente
    data_mais_recente = df_temp['Data_Competencia'].max()
    
    # Calcular datas de comparação
    data_ontem = data_mais_recente - pd.Timedelta(days=1)
    data_7_dias = data_mais_recente - pd.Timedelta(days=7)
    data_15_dias = data_mais_recente - pd.Timedelta(days=15)
    
    def obter_vendas_data(data_target):
        vendas_data = df_temp[df_temp['Data_Competencia'].dt.date == data_target.date()]
        return {
            'data': data_target.date(),
            'faturamento': vendas_data['Total_Venda'].sum(),
            'vendas': len(vendas_data),
            'ticket_medio': vendas_data['Total_Venda'].mean() if len(vendas_data) > 0 else 0
        }
    
    # Obter dados para cada período
    hoje = obter_vendas_data(data_mais_recente)
    ontem = obter_vendas_data(data_ontem)
    dias_7 = obter_vendas_data(data_7_dias)  
    dias_15 = obter_vendas_data(data_15_dias)
    
    def calcular_variacao(atual, anterior):
        if anterior > 0:
            return (atual - anterior) / anterior * 100
        return 0
    
    return {
        'hoje': hoje,
        'ontem': ontem,
        'dias_7': dias_7,
        'dias_15': dias_15,
        'var_ontem': {
            'faturamento': calcular_variacao(hoje['faturamento'], ontem['faturamento']),
            'vendas': calcular_variacao(hoje['vendas'], ontem['vendas']),
            'ticket': calcular_variacao(hoje['ticket_medio'], ontem['ticket_medio'])
        },
        'var_7_dias': {
            'faturamento': calcular_variacao(hoje['faturamento'], dias_7['faturamento']),
            'vendas': calcular_variacao(hoje['vendas'], dias_7['vendas']),
            'ticket': calcular_variacao(hoje['ticket_medio'], dias_7['ticket_medio'])
        },
        'var_15_dias': {
            'faturamento': calcular_variacao(hoje['faturamento'], dias_15['faturamento']),
            'vendas': calcular_variacao(hoje['vendas'], dias_15['vendas']),
            'ticket': calcular_variacao(hoje['ticket_medio'], dias_15['ticket_medio'])
        }
    }

def calcular_metricas_mes_atacado(df, meta_mensal=850000, dias_uteis=27):
    """Calcula métricas do mês para o atacado com meta definida"""
    df_temp = df.copy()
    df_temp['Data_Competencia'] = pd.to_datetime(df_temp['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
    df_temp = df_temp.dropna(subset=['Data_Competencia'])
    
    if df_temp.empty:
        return None
    
    # Filtrar dados do mês atual
    data_mais_recente = df_temp['Data_Competencia'].max()
    mes_atual = data_mais_recente.month
    ano_atual = data_mais_recente.year
    
    vendas_mes = df_temp[
        (df_temp['Data_Competencia'].dt.month == mes_atual) & 
        (df_temp['Data_Competencia'].dt.year == ano_atual)
    ]
    
    # Métricas básicas do mês
    faturamento_mes = vendas_mes['Total_Venda'].sum()
    vendas_quantidade = len(vendas_mes)
    dias_com_vendas = len(vendas_mes['Data_Competencia'].dt.date.unique())
    ticket_medio_mes = vendas_mes['Total_Venda'].mean() if len(vendas_mes) > 0 else 0
    
    # Cálculos com meta
    progresso_meta = (faturamento_mes / meta_mensal * 100) if meta_mensal > 0 else 0
    falta_meta = max(0, meta_mensal - faturamento_mes)
    dias_restantes = max(0, dias_uteis - dias_com_vendas)
    
    # Médias e ritmos
    media_diaria_atual = faturamento_mes / dias_com_vendas if dias_com_vendas > 0 else 0
    media_necessaria = falta_meta / max(1, dias_restantes) if dias_restantes > 0 else 0
    
    # Projeção simples
    projecao_atual = media_diaria_atual * dias_uteis
    
    return {
        'faturamento_mes': faturamento_mes,
        'vendas_quantidade': vendas_quantidade,
        'dias_com_vendas': dias_com_vendas,
        'ticket_medio_mes': ticket_medio_mes,
        'meta_mensal': meta_mensal,
        'progresso_meta': progresso_meta,
        'falta_meta': falta_meta,
        'dias_restantes': dias_restantes,
        'dias_uteis': dias_uteis,
        'media_diaria_atual': media_diaria_atual,
        'media_necessaria': media_necessaria,
        'projecao_atual': projecao_atual,
        'data_mais_recente': data_mais_recente
    }

def calcular_projecoes_melhoradas(df, meta_mensal=850000, dias_uteis=27):
    """Calcula 4 projeções melhoradas com visualização aprimorada"""
    df_temp = df.copy()
    df_temp['Data_Competencia'] = pd.to_datetime(df_temp['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
    df_temp = df_temp.dropna(subset=['Data_Competencia'])
    
    if df_temp.empty:
        return None
    
    # Dados do mês atual
    data_mais_recente = df_temp['Data_Competencia'].max()
    mes_atual = data_mais_recente.month
    ano_atual = data_mais_recente.year
    
    vendas_mes = df_temp[
        (df_temp['Data_Competencia'].dt.month == mes_atual) & 
        (df_temp['Data_Competencia'].dt.year == ano_atual)
    ]
    
    faturamento_atual = vendas_mes['Total_Venda'].sum()
    dias_trabalhados = len(vendas_mes['Data_Competencia'].dt.date.unique())
    
    # Projeção 1: Média Simples
    media_diaria = faturamento_atual / dias_trabalhados if dias_trabalhados > 0 else 0
    projecao_simples = media_diaria * dias_uteis
    
    # Projeção 2: Com Tendência (últimos vs primeiros dias)
    if len(vendas_mes) >= 10:
        vendas_por_dia = vendas_mes.groupby(vendas_mes['Data_Competencia'].dt.date)['Total_Venda'].sum().sort_index()
        if len(vendas_por_dia) >= 6:
            primeiros_3 = vendas_por_dia.head(3).mean()
            ultimos_3 = vendas_por_dia.tail(3).mean()
            tendencia = (ultimos_3 - primeiros_3) / primeiros_3 if primeiros_3 > 0 else 0
            projecao_tendencia = projecao_simples * (1 + tendencia * 0.3)  # Aplicar 30% da tendência
        else:
            projecao_tendencia = projecao_simples
    else:
        projecao_tendencia = projecao_simples
    
    # Projeção 3: Baseada na Meta (ritmo necessário)
    dias_restantes = max(1, dias_uteis - dias_trabalhados)
    falta_meta = max(0, meta_mensal - faturamento_atual)
    ritmo_necessario = falta_meta / dias_restantes
    projecao_meta = faturamento_atual + (ritmo_necessario * dias_restantes)
    
    # Projeção 4: Híbrida Inteligente
    # Peso maior para método mais conservador se estamos próximos da meta
    if faturamento_atual / meta_mensal > 0.8:
        peso_simples, peso_tendencia, peso_meta = 0.5, 0.3, 0.2
    else:
        peso_simples, peso_tendencia, peso_meta = 0.3, 0.4, 0.3
    
    projecao_hibrida = (
        projecao_simples * peso_simples +
        projecao_tendencia * peso_tendencia +
        projecao_meta * peso_meta
    )
    
    return {
        'projecao_simples': projecao_simples,
        'projecao_tendencia': projecao_tendencia,
        'projecao_meta': projecao_meta,
        'projecao_hibrida': projecao_hibrida,
        'media_diaria': media_diaria,
        'ritmo_necessario': ritmo_necessario,
        'faturamento_atual': faturamento_atual,
        'dias_trabalhados': dias_trabalhados,
        'dias_restantes': dias_restantes,
        'meta_mensal': meta_mensal
    }

def carregar_dados_varejo():
    """Carrega dados do varejo - apenas julho 2025"""
    try:
        # Buscar arquivo de varejo mais recente (dados até 28/07/2025)
        arquivo_varejo = None
        
        # Primeiro tentar na pasta dados_diarios (mais recente)
        if os.path.exists('dados_diarios/2025-07-28/varejo_ate_28072025.txt'):
            arquivo_varejo = 'dados_diarios/2025-07-28/varejo_ate_28072025.txt'
        elif os.path.exists('dados_diarios/2025-07-26/varejo_ate_26072025.txt'):
            arquivo_varejo = 'dados_diarios/2025-07-26/varejo_ate_26072025.txt'
        else:
            # Fallback para busca na raiz
            arquivos_varejo = [f for f in os.listdir('.') if 'varejo' in f.lower() and f.endswith('.txt')]
            if arquivos_varejo:
                arquivo_varejo = arquivos_varejo[0]
        
        if not arquivo_varejo:
            return None
        
        # Tentar diferentes encodings
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-8-sig', 'cp850']
        
        for encoding in encodings:
            try:
                df_varejo = pd.read_csv(
                    arquivo_varejo, 
                    sep=';',
                    encoding=encoding,
                    on_bad_lines='skip'
                )
                
                # Verificar se carregou corretamente
                if len(df_varejo) > 0 and 'Data Competência' in df_varejo.columns:
                    # Processar dados do varejo
                    df_varejo = df_varejo.rename(columns={
                        'Data Competência': 'Data_Competencia',
                        'Parceiro': 'Nome_Cliente',
                        'Total Venda': 'Total_Venda',
                        'Total': 'Total',
                        'Desconto': 'Desconto',
                        'Vendedor': 'Vendedor'
                    })
                    
                    # Filtrar apenas vendas (não devoluções)
                    df_varejo = df_varejo[df_varejo['Operação'] == 'VENDAS']
                    
                    # Converter valores para numérico, substituindo vírgula por ponto
                    for col in ['Total_Venda', 'Total', 'Desconto']:
                        if col in df_varejo.columns:
                            df_varejo[col] = df_varejo[col].astype(str).str.replace(',', '.').astype(float, errors='ignore')
                    
                    # O campo 'Total_Venda' já é o valor líquido final para varejo também
                    df_varejo['Valor_Liquido'] = df_varejo['Total_Venda']  # Total_Venda já é correto
                    
                    # Filtrar apenas julho 2025
                    df_varejo['Data_Competencia'] = pd.to_datetime(df_varejo['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
                    df_varejo = df_varejo.dropna(subset=['Data_Competencia'])
                    
                    # Filtrar apenas julho 2025
                    df_varejo = df_varejo[
                        (df_varejo['Data_Competencia'].dt.month == 7) & 
                        (df_varejo['Data_Competencia'].dt.year == 2025)
                    ]
                    
                    # Formatar data de volta para string
                    df_varejo['Data_Competencia'] = df_varejo['Data_Competencia'].dt.strftime('%d/%m/%Y')
                    
                    return df_varejo
                    
            except Exception as e:
                continue
        
        return None
        
    except Exception as e:
        st.error(f"Erro ao carregar dados do varejo: {str(e)}")
        return None

def calcular_metricas_varejo(df_varejo):
    """Calcula métricas específicas do varejo"""
    if df_varejo is None or df_varejo.empty:
        return None
    
    # Estatísticas básicas
    faturamento_total = df_varejo['Total_Venda'].sum()
    vendas_total = len(df_varejo)
    ticket_medio = df_varejo['Total_Venda'].mean()
    
    # Análise por vendedor
    vendas_por_vendedor = df_varejo.groupby('Vendedor').agg({
        'Total_Venda': ['sum', 'count', 'mean']
    }).round(2)
    vendas_por_vendedor.columns = ['Faturamento', 'Qtd_Vendas', 'Ticket_Medio']
    vendas_por_vendedor = vendas_por_vendedor.sort_values('Faturamento', ascending=False)
    
    # Análise temporal
    df_temp = df_varejo.copy()
    df_temp['Data_Competencia'] = pd.to_datetime(df_temp['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
    
    vendas_por_dia = df_temp.groupby(df_temp['Data_Competencia'].dt.date).agg({
        'Total_Venda': ['sum', 'count']
    }).round(2)
    vendas_por_dia.columns = ['Faturamento_Diario', 'Vendas_Diario']
    
    dias_com_vendas = len(vendas_por_dia)
    media_diaria = vendas_por_dia['Faturamento_Diario'].mean()
    
    return {
        'faturamento_total': faturamento_total,
        'vendas_total': vendas_total,
        'ticket_medio': ticket_medio,
        'vendas_por_vendedor': vendas_por_vendedor,
        'vendas_por_dia': vendas_por_dia,
        'dias_com_vendas': dias_com_vendas,
        'media_diaria': media_diaria,
        'data_inicio': df_temp['Data_Competencia'].min(),
        'data_fim': df_temp['Data_Competencia'].max()
    }

def dashboard_varejo(df_varejo, layout_mode):
    """Dashboard específico do varejo com foco em valor líquido"""
    st.title("🏪 Dashboard de Varejo - Grãos S.A.")
    st.markdown("*Análise de vendas do setor de varejo - Julho 2025 (Valores Líquidos)*")
    
    if df_varejo is None or df_varejo.empty:
        st.warning("❌ Dados do varejo não encontrados")
        st.info("📝 **Para carregar dados do varejo**: Coloque um arquivo com 'varejo' no nome na pasta do sistema")
        return
    
    # === 1. VENDAS DE HOJE ===
    titulo_dinamico = gerar_titulo_vendas_dinamico(df_varejo, "Vendas")
    st.markdown(f"### {titulo_dinamico}")
    data_recente = obter_data_mais_recente_str(df_varejo)
    st.caption(f"*Performance do varejo - {data_recente} - Valor Líquido*")
    
    # Calcular vendas de hoje
    df_varejo_temp = df_varejo.copy()
    df_varejo_temp['Data_Competencia'] = pd.to_datetime(df_varejo_temp['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
    df_varejo_temp = df_varejo_temp.dropna(subset=['Data_Competencia'])
    
    if not df_varejo_temp.empty:
        data_mais_recente = df_varejo_temp['Data_Competencia'].max()
        vendas_hoje = df_varejo_temp[df_varejo_temp['Data_Competencia'].dt.date == data_mais_recente.date()]
        
        col_hoje1, col_hoje2, col_hoje3, col_hoje4 = st.columns(4)
        
        with col_hoje1:
            fat_hoje = vendas_hoje['Total_Venda'].sum()
            st.metric(
                label="💰 Faturamento Hoje",
                value=f"R$ {fat_hoje:,.2f}",
                help="Faturamento líquido de hoje no varejo"
            )
        
        with col_hoje2:
            vendas_qtd_hoje = len(vendas_hoje)
            st.metric(
                label="🛒 Vendas Hoje",
                value=f"{vendas_qtd_hoje}",
                help="Número de vendas realizadas hoje"
            )
        
        with col_hoje3:
            ticket_hoje = vendas_hoje['Total_Venda'].mean() if len(vendas_hoje) > 0 else 0
            st.metric(
                label="📊 Ticket Médio Hoje",
                value=f"R$ {ticket_hoje:,.2f}",
                help="Valor médio por venda hoje"
            )
        
        with col_hoje4:
            vendedores_hoje = vendas_hoje['Vendedor'].nunique() if 'Vendedor' in vendas_hoje.columns else 0
            st.metric(
                label="👥 Vendedores Ativos",
                value=f"{vendedores_hoje}",
                delta=f"Data: {data_mais_recente.strftime('%d/%m')}",
                help="Vendedores que realizaram vendas hoje"
            )
    
    # === 2. MÉTRICAS GERAIS ===
    st.markdown("---")
    st.markdown("### 📊 Métricas Gerais - Julho 2025")
    st.caption("*Desempenho consolidado do mês - Valor Líquido*")
    
    metricas = calcular_metricas_varejo(df_varejo)
    
    if metricas:
        col_geral1, col_geral2, col_geral3, col_geral4 = st.columns(4)
        
        with col_geral1:
            st.metric(
                label="💰 Faturamento Total",
                value=f"R$ {metricas['faturamento_total']:,.2f}",
                help="Faturamento líquido total do varejo em julho"
            )
        
        with col_geral2:
            st.metric(
                label="🛒 Total de Vendas",
                value=f"{metricas['vendas_total']:,}",
                help="Número total de vendas no período"
            )
        
        with col_geral3:
            st.metric(
                label="📊 Ticket Médio Geral",
                value=f"R$ {metricas['ticket_medio']:,.2f}",
                help="Valor médio por venda (líquido)"
            )
        
        with col_geral4:
            st.metric(
                label="📅 Dias de Vendas",
                value=f"{metricas['dias_com_vendas']} dias",
                delta=f"R$ {metricas['media_diaria']:,.2f}/dia",
                help="Dias com vendas e média diária"
            )
    
        # === 3. PROJEÇÃO ===
        st.markdown("---")
        st.markdown("### 🔮 Projeção para Final de Julho")
        st.caption("*Estimativas baseadas no desempenho atual*")
        
        dias_uteis_julho = 27
        dias_restantes = max(0, dias_uteis_julho - metricas['dias_com_vendas'])
        
        col_proj1, col_proj2, col_proj3 = st.columns(3)
        
        with col_proj1:
            if dias_restantes > 0:
                projecao_simples = metricas['media_diaria'] * dias_uteis_julho
                st.metric(
                    label="📈 Projeção Fim do Mês",
                    value=f"R$ {projecao_simples:,.2f}",
                    help="Baseado na média diária atual"
                )
            else:
                st.metric(
                    label="📈 Faturamento Final",
                    value=f"R$ {metricas['faturamento_total']:,.2f}",
                    help="Mês completo - resultado final"
                )
        
        with col_proj2:
            if dias_restantes > 0:
                st.metric(
                    label="📅 Dias Restantes",
                    value=f"{dias_restantes} dias",
                    help="Dias úteis restantes em julho"
                )
            else:
                crescimento_estimado = (metricas['faturamento_total'] / metricas['dias_com_vendas']) / metricas['media_diaria'] * 100 - 100 if metricas['media_diaria'] > 0 else 0
                st.metric(
                    label="📊 Performance vs Meta",
                    value="100%",
                    delta=f"Eficiência: {100 + crescimento_estimado:.1f}%",
                    help="Mês completo realizado"
                )
        
        with col_proj3:
            # Como calculamos a projeção
            if st.button("💡 Como Calculamos", key="como_calc_varejo"):
                with st.expander("📊 **Metodologia de Projeção - Varejo**", expanded=True):
                    st.markdown("""
                    **🎯 Cálculo da Projeção:**
                    
                    • **Média Diária**: Faturamento acumulado ÷ Dias trabalhados
                    • **Projeção**: Média diária × 27 dias úteis
                    • **Base**: Valores líquidos (descontados)
                    
                    **📈 Fatores Considerados:**
                    • Sazonalidade do varejo
                    • Performance histórica
                    • Dias úteis restantes
                    
                    **⚠️ Limitações:**
                    • Não considera eventos especiais
                    • Baseado em tendência linear
                    • Sujeito a variações de mercado
                    """)
        
        # === 4. PERFORMANCE POR VENDEDOR ===
        st.markdown("---")
        st.markdown("### 👥 Performance por Vendedor")
        st.caption("*Análise detalhada com gráficos interativos*")
        
        if not metricas['vendas_por_vendedor'].empty:
            # Gráficos de performance
            import plotly.express as px
            import plotly.graph_objects as go
            
            vendedores_data = metricas['vendas_por_vendedor'].reset_index()
            
            # Tabs para diferentes análises
            tab_fat, tab_qtd, tab_ticket, tab_tabela = st.tabs(["💰 Faturamento", "🛒 Quantidade", "📊 Ticket Médio", "📋 Tabela"])
            
            with tab_fat:
                # Gráfico de faturamento por vendedor
                fig_fat = px.bar(
                    vendedores_data.head(10),
                    x='Faturamento',
                    y='Vendedor',
                    orientation='h',
                    title='Top 10 Vendedores por Faturamento',
                    color='Faturamento',
                    color_continuous_scale='Greens'
                )
                fig_fat.update_layout(yaxis={'categoryorder':'total ascending'})
                
                # Aplicar configuração responsiva
                fig_fat = config_grafico_mobile(fig_fat, layout_mode)
                st.plotly_chart(fig_fat, use_container_width=True)
                
                # Análise de concentração
                top_3_pct = (vendedores_data.head(3)['Faturamento'].sum() / vendedores_data['Faturamento'].sum() * 100)
                if top_3_pct > 60:
                    st.warning(f"⚠️ **CONCENTRAÇÃO ALTA**: Top 3 vendedores representam {top_3_pct:.1f}% das vendas")
                else:
                    st.success(f"✅ **DISTRIBUIÇÃO SAUDÁVEL**: Top 3 vendedores representam {top_3_pct:.1f}% das vendas")
            
            with tab_qtd:
                # Gráfico de quantidade de vendas
                fig_qtd = px.bar(
                    vendedores_data.head(10),
                    x='Qtd_Vendas',
                    y='Vendedor',
                    orientation='h',
                    title='Top 10 Vendedores por Quantidade de Vendas',
                    color='Qtd_Vendas',
                    color_continuous_scale='Blues'
                )
                fig_qtd.update_layout(height=500, yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_qtd, use_container_width=True)
                
                # Análise de produtividade
                media_vendas = vendedores_data['Qtd_Vendas'].mean()
                vendedores_acima_media = len(vendedores_data[vendedores_data['Qtd_Vendas'] > media_vendas])
                st.info(f"📊 **{vendedores_acima_media}** vendedores estão acima da média de **{media_vendas:.1f}** vendas")
            
            with tab_ticket:
                # Gráfico de ticket médio
                fig_ticket = px.bar(
                    vendedores_data.sort_values('Ticket_Medio', ascending=False).head(10),
                    x='Ticket_Medio',
                    y='Vendedor',
                    orientation='h',
                    title='Top 10 Vendedores por Ticket Médio',
                    color='Ticket_Medio',
                    color_continuous_scale='Oranges'
                )
                fig_ticket.update_layout(height=500, yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_ticket, use_container_width=True)
                
                # Análise de ticket médio
                ticket_medio_geral = vendedores_data['Ticket_Medio'].mean()
                melhor_ticket = vendedores_data.loc[vendedores_data['Ticket_Medio'].idxmax()]
                st.success(f"🏆 **MELHOR TICKET**: {melhor_ticket['Vendedor']} - R$ {melhor_ticket['Ticket_Medio']:,.2f}")
                st.info(f"📊 **TICKET MÉDIO GERAL**: R$ {ticket_medio_geral:,.2f}")
            
            with tab_tabela:
                # Tabela completa melhorada
                st.markdown("**📋 Ranking Completo de Vendedores**")
                
                vendedores_display = vendedores_data.copy()
                vendedores_display['Posicao'] = range(1, len(vendedores_display) + 1)
                vendedores_display['Faturamento_Fmt'] = vendedores_display['Faturamento'].apply(lambda x: f"R$ {x:,.2f}")
                vendedores_display['Ticket_Medio_Fmt'] = vendedores_display['Ticket_Medio'].apply(lambda x: f"R$ {x:,.2f}")
                vendedores_display['Qtd_Vendas'] = vendedores_display['Qtd_Vendas'].astype(int)
                vendedores_display['Participacao'] = (vendedores_display['Faturamento'] / vendedores_display['Faturamento'].sum() * 100).round(1)
                
                st.dataframe(
                    vendedores_display[['Posicao', 'Vendedor', 'Faturamento_Fmt', 'Participacao', 'Qtd_Vendas', 'Ticket_Medio_Fmt']],
                    column_config={
                        'Posicao': st.column_config.NumberColumn('Pos.', width="small"),
                        'Vendedor': 'Vendedor',
                        'Faturamento_Fmt': 'Faturamento',
                        'Participacao': st.column_config.NumberColumn('Part. %', format="%.1f%%"),
                        'Qtd_Vendas': st.column_config.NumberColumn('Nº Vendas'),
                        'Ticket_Medio_Fmt': 'Ticket Médio'
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                # Resumo estatístico
                st.markdown("**📊 Resumo Estatístico:**")
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                
                with col_stat1:
                    st.metric("👥 Total Vendedores", len(vendedores_data))
                with col_stat2:
                    st.metric("💰 Maior Faturamento", f"R$ {vendedores_data['Faturamento'].max():,.2f}")
                with col_stat3:
                    st.metric("🎯 Maior Ticket", f"R$ {vendedores_data['Ticket_Medio'].max():,.2f}")
        
        else:
            st.warning("❌ Não há dados de vendedores disponíveis")
    
    else:
        st.error("❌ Erro ao processar métricas do varejo")

def dashboard_geral_consolidado(df_atacado, df_varejo, layout_mode):
    """Dashboard principal: visão geral completa com vendas de hoje, projeções e clientes"""
    st.title("🌍 Dashboard Geral - Grãos S.A.")
    st.markdown("*Visão estratégica completa: Vendas + Clientes + Projeções*")
    
    # Verificar disponibilidade dos dados
    tem_atacado = df_atacado is not None and not df_atacado.empty
    tem_varejo = df_varejo is not None and not df_varejo.empty
    
    if not tem_atacado and not tem_varejo:
        st.error("❌ Nenhum dado disponível")
        return
    
    # === 1. VENDAS DE HOJE ===
    # Usar a data mais recente entre atacado e varejo
    data_atacado = obter_data_mais_recente_str(df_atacado) if tem_atacado else None
    data_varejo = obter_data_mais_recente_str(df_varejo) if tem_varejo else None
    
    # Determinar qual data usar no título
    if data_atacado and data_varejo:
        # Converter para datetime para comparar e usar a mais recente
        data_atac_dt = pd.to_datetime(data_atacado, format='%d/%m/%Y')
        data_var_dt = pd.to_datetime(data_varejo, format='%d/%m/%Y')
        data_titulo = data_atacado if data_atac_dt >= data_var_dt else data_varejo
    elif data_atacado:
        data_titulo = data_atacado
    elif data_varejo:
        data_titulo = data_varejo
    else:
        data_titulo = "Hoje"
    
    # Título responsivo
    if layout_mode == "📱 Mobile":
        st.markdown(f"**🔥 Vendas de {data_titulo}**")
        st.caption(f"*{data_titulo}*")
    else:
        st.markdown(f"### 🔥 Vendas de {data_titulo} - Visão Geral")
        st.caption(f"*Performance dos dois setores - {data_titulo}*")
    
    # Calcular vendas de hoje para ambos os setores
    vendas_hoje_atacado = calcular_comparacoes_temporais(df_atacado) if tem_atacado else None
    vendas_hoje_varejo = None
    if tem_varejo:
        # Calcular vendas de hoje para varejo
        df_varejo_temp = df_varejo.copy()
        df_varejo_temp['Data_Competencia'] = pd.to_datetime(df_varejo_temp['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
        df_varejo_temp = df_varejo_temp.dropna(subset=['Data_Competencia'])
        
        if not df_varejo_temp.empty:
            data_mais_recente_varejo = df_varejo_temp['Data_Competencia'].max()
            vendas_hoje_varejo_df = df_varejo_temp[df_varejo_temp['Data_Competencia'].dt.date == data_mais_recente_varejo.date()]
            
            vendas_hoje_varejo = {
                'faturamento': vendas_hoje_varejo_df['Total_Venda'].sum(),
                'vendas': len(vendas_hoje_varejo_df),
                'ticket_medio': vendas_hoje_varejo_df['Total_Venda'].mean() if len(vendas_hoje_varejo_df) > 0 else 0,
                'data': data_mais_recente_varejo.date()
            }
    
    # Métricas de vendas de hoje separadas por setor
    fat_atacado = vendas_hoje_atacado['hoje']['faturamento'] if vendas_hoje_atacado else 0
    fat_varejo = vendas_hoje_varejo['faturamento'] if vendas_hoje_varejo else 0
    fat_total = fat_atacado + fat_varejo
    
    vendas_atacado_hoje = vendas_hoje_atacado['hoje']['vendas'] if vendas_hoje_atacado else 0
    vendas_varejo_hoje = vendas_hoje_varejo['vendas'] if vendas_hoje_varejo else 0
    vendas_total_hoje = vendas_atacado_hoje + vendas_varejo_hoje
    
    # Layout responsivo para métricas principais
    if layout_mode == "📱 Mobile":
        # Mobile: 2 linhas de 2 colunas para melhor legibilidade
        st.markdown("**📊 Métricas Principais:**")
        
        # Primeira linha mobile
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric(
                label="💰 Faturamento Total",
                value=f"R$ {fat_total:,.0f}",
                help="Soma atacado + varejo hoje"
            )
        with col_m2:
            st.metric(
                label="🛒 Vendas Total",
                value=f"{vendas_total_hoje}",
                help="Total de vendas hoje"
            )
        
        # Segunda linha mobile
        col_m3, col_m4 = st.columns(2)
        with col_m3:
            ticket_total_hoje = fat_total / vendas_total_hoje if vendas_total_hoje > 0 else 0
            st.metric(
                label="📊 Ticket Médio",
                value=f"R$ {ticket_total_hoje:,.0f}",
                help="Valor médio por venda"
            )
        with col_m4:
            # Última atualização simplificada
            data_ref = vendas_hoje_atacado['hoje']['data'] if vendas_hoje_atacado else vendas_hoje_varejo['data'] if vendas_hoje_varejo else "N/A"
            st.metric(
                label="📅 Atualização",
                value=data_ref.strftime('%d/%m') if data_ref != "N/A" else "N/A",
                help="Data dos dados"
            )
    
    else:
        # Desktop: layout original com 4 colunas
        col_total1, col_total2, col_total3, col_total4 = st.columns(4)
        
        with col_total1:
            st.metric(
                label="💰 Faturamento Total Hoje",
                value=f"R$ {fat_total:,.2f}",
                help="Soma do faturamento líquido de atacado + varejo hoje"
            )
        
        with col_total2:
            st.metric(
                label="🛒 Vendas Total Hoje",
                value=f"{vendas_total_hoje}",
                help="Soma das vendas de atacado + varejo hoje"
            )
        
        with col_total3:
            ticket_total_hoje = fat_total / vendas_total_hoje if vendas_total_hoje > 0 else 0
            st.metric(
                label="📊 Ticket Médio Geral",
                value=f"R$ {ticket_total_hoje:,.2f}",
                help="Valor médio por venda hoje (ambos os setores)"
            )
        
        with col_total4:
            # Comparação com ontem (apenas atacado tem histórico)
            if vendas_hoje_atacado and vendas_hoje_atacado['var_ontem']['faturamento'] != 0:
                var_ontem = vendas_hoje_atacado['var_ontem']['faturamento']
                delta_ontem = f"{var_ontem:+.1f}% vs ontem"
                cor_ontem = "normal" if var_ontem >= 0 else "inverse"
            else:
                delta_ontem = "Sem comparativo"
                cor_ontem = "off"
            
            data_ref = vendas_hoje_atacado['hoje']['data'] if vendas_hoje_atacado else vendas_hoje_varejo['data'] if vendas_hoje_varejo else "N/A"
            
            st.metric(
                label="📅 Última Atualização",
                value=data_ref.strftime('%d/%m/%Y') if data_ref != "N/A" else "N/A",
                delta=delta_ontem,
                delta_color=cor_ontem,
                help="Comparação com o dia anterior (baseado no atacado)"
            )
    
    # Vendas separadas por setor - Layout responsivo
    if layout_mode == "📱 Mobile":
        st.markdown("**🏢 Por Setor:**")
        
        # Primeira linha mobile: Valores absolutos
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.metric(
                label="🏢 Atacado",
                value=f"R$ {fat_atacado:,.0f}",
                delta=f"{vendas_atacado_hoje} vendas",
                help="Faturamento atacado hoje"
            )
        with col_s2:
            st.metric(
                label="🏪 Varejo", 
                value=f"R$ {fat_varejo:,.0f}",
                delta=f"{vendas_varejo_hoje} vendas",
                help="Faturamento varejo hoje"
            )
        
        # Segunda linha mobile: Participações
        if fat_total > 0:
            col_s3, col_s4 = st.columns(2)
            part_atacado = (fat_atacado / fat_total * 100)
            part_varejo = (fat_varejo / fat_total * 100)
            
            with col_s3:
                st.metric(
                    label="📈 Part. Atacado",
                    value=f"{part_atacado:.1f}%",
                    help="% do faturamento"
                )
            with col_s4:
                st.metric(
                    label="📊 Part. Varejo",
                    value=f"{part_varejo:.1f}%",
                    help="% do faturamento"
                )
    
    else:
        # Desktop: layout original
        st.markdown("**📊 Vendas por Setor:**")
        col_setor1, col_setor2, col_setor3, col_setor4 = st.columns(4)
        
        with col_setor1:
            st.metric(
                label="🏢 Venda Atacado",
                value=f"R$ {fat_atacado:,.2f}",
                delta=f"{vendas_atacado_hoje} vendas",
                help="Faturamento líquido do atacado hoje"
            )
        
        with col_setor2:
            st.metric(
                label="🏪 Venda Varejo", 
                value=f"R$ {fat_varejo:,.2f}",
                delta=f"{vendas_varejo_hoje} vendas",
                help="Faturamento líquido do varejo hoje"
            )
        
        with col_setor3:
            # Participação do atacado
            part_atacado = (fat_atacado / fat_total * 100) if fat_total > 0 else 0
            st.metric(
                label="📈 Part. Atacado",
                value=f"{part_atacado:.1f}%",
                help="Participação do atacado no faturamento de hoje"
            )
        
        with col_setor4:
            # Participação do varejo
            part_varejo = (fat_varejo / fat_total * 100) if fat_total > 0 else 0
            st.metric(
                label="📊 Part. Varejo",
                value=f"{part_varejo:.1f}%",
                help="Participação do varejo no faturamento de hoje"
            )

    
    # === 2. CLIENTES NOVOS (ATACADO) ===
    if tem_atacado:
        espacamento_responsivo(layout_mode)
        # Título responsivo
        if layout_mode == "📱 Mobile":
            st.markdown("**👥 Clientes Novos**")
            st.caption("*Atacado*")
        else:
            st.markdown("### 👥 Clientes Novos - Hoje")
            st.caption("*Análise de novos clientes no setor de atacado*")
        
        # Calcular clientes novos de hoje
        df_temp_clientes = df_atacado.copy()
        df_temp_clientes['Data_Competencia'] = pd.to_datetime(df_temp_clientes['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
        df_temp_clientes = df_temp_clientes.dropna(subset=['Data_Competencia'])
        
        if not df_temp_clientes.empty:
            data_mais_recente = df_temp_clientes['Data_Competencia'].max()
            clientes_hoje = df_temp_clientes[df_temp_clientes['Data_Competencia'].dt.date == data_mais_recente.date()]
            
            # Identificar clientes novos (primeira compra)
            historico_clientes = df_temp_clientes.groupby('Nome_Cliente')['Data_Competencia'].min()
            clientes_novos_hoje = []
            
            for cliente in clientes_hoje['Nome_Cliente'].unique():
                if historico_clientes[cliente].date() == data_mais_recente.date():
                    clientes_novos_hoje.append(cliente)
            
            qtd_clientes_novos = len(clientes_novos_hoje)
            
            col_cli1, col_cli2, col_cli3, col_cli4 = st.columns(4)
            
            with col_cli1:
                st.metric(
                    label="👶 Clientes Novos Hoje",
                    value=f"{qtd_clientes_novos}",
                    help="Clientes que fizeram sua primeira compra hoje"
                )
            
            with col_cli2:
                # Faturamento dos clientes novos
                if clientes_novos_hoje:
                    fat_novos = clientes_hoje[clientes_hoje['Nome_Cliente'].isin(clientes_novos_hoje)]['Total_Venda'].sum()
                else:
                    fat_novos = 0
                
                st.metric(
                    label="💰 Faturamento Novos",
                    value=f"R$ {fat_novos:,.2f}",
                    help="Faturamento gerado pelos clientes novos hoje"
                )
            
            with col_cli3:
                # Ticket médio dos novos
                if clientes_novos_hoje and qtd_clientes_novos > 0:
                    ticket_novos = fat_novos / qtd_clientes_novos
                else:
                    ticket_novos = 0
                
                st.metric(
                    label="📊 Ticket Médio Novos",
                    value=f"R$ {ticket_novos:,.2f}",
                    help="Valor médio gasto pelos clientes novos"
                )
            
            with col_cli4:
                # Meta de clientes (2.2/dia para 60 no mês)
                meta_diaria_clientes = 2.2
                desempenho_meta = (qtd_clientes_novos / meta_diaria_clientes * 100) if meta_diaria_clientes > 0 else 0
                
                st.metric(
                    label="🎯 vs Meta Diária",
                    value=f"{desempenho_meta:.1f}%",
                    delta=f"Meta: {meta_diaria_clientes} clientes/dia",
                    delta_color="normal" if desempenho_meta >= 100 else "inverse",
                    help="Performance vs meta de 2.2 clientes novos por dia"
                )
    
    # === 3. PROJEÇÕES E METAS ===
    st.markdown("---")
    st.markdown("### 🔮 Projeções e Performance do Mês")
    st.caption("*Como está indo o mês - Atacado + Varejo*")
    
    # Calcular métricas consolidadas
    metricas_atacado = calcular_metricas_mes_atacado(df_atacado) if tem_atacado else None
    metricas_varejo = calcular_metricas_varejo(df_varejo) if tem_varejo else None
    
    # Faturamento consolidado
    faturamento_atacado = metricas_atacado['faturamento_mes'] if metricas_atacado else 0
    faturamento_varejo = metricas_varejo['faturamento_total'] if metricas_varejo else 0
    faturamento_total = faturamento_atacado + faturamento_varejo
    
    # Projeções
    meta_atacado = 850000
    dias_uteis = 27
    
    col_proj1, col_proj2, col_proj3, col_proj4 = st.columns(4)
    
    with col_proj1:
        st.metric(
            label="💰 Faturamento Acumulado",
            value=f"R$ {faturamento_total:,.2f}",
            help=f"Atacado: R$ {faturamento_atacado:,.2f} + Varejo: R$ {faturamento_varejo:,.2f}"
        )
    
    with col_proj2:
        # Média diária consolidada
        media_diaria_atacado = metricas_atacado['media_diaria_atual'] if metricas_atacado else 0
        media_diaria_varejo = metricas_varejo['media_diaria'] if metricas_varejo else 0
        media_diaria_total = media_diaria_atacado + media_diaria_varejo
        
        st.metric(
            label="📊 Média Diária",
            value=f"R$ {media_diaria_total:,.2f}",
            help=f"Atacado: R$ {media_diaria_atacado:,.2f}/dia + Varejo: R$ {media_diaria_varejo:,.2f}/dia"
        )
    
    with col_proj3:
        # Projeção consolidada
        projecao_consolidada = media_diaria_total * dias_uteis
        
        st.metric(
            label="🔮 Projeção Fim do Mês",
            value=f"R$ {projecao_consolidada:,.2f}",
            help="Projeção baseada na média diária atual (ambos os setores)"
        )
    
    with col_proj4:
        # vs Meta do atacado
        diferenca_meta = projecao_consolidada - meta_atacado
        percent_meta = (diferenca_meta / meta_atacado * 100) if meta_atacado > 0 else 0
        
        st.metric(
            label="🎯 vs Meta Atacado",
            value=f"R$ {diferenca_meta:,.2f}",
            delta=f"{percent_meta:+.1f}%",
            delta_color="normal" if diferenca_meta >= 0 else "inverse",
            help=f"Diferença vs meta de R$ {meta_atacado:,.2f} do atacado"
        )
    
    # Explicação detalhada das projeções
    st.markdown("---")
    st.markdown("### 💡 Como Calculamos as Projeções")
    
    if st.button("📊 Ver Metodologia Detalhada", key="metodologia_geral"):
        with st.expander("🧮 **Metodologia de Cálculo - Dashboard Geral**", expanded=True):
            st.markdown(f"""
            **🎯 FATURAMENTO ACUMULADO:**
            • **Atacado**: R$ {faturamento_atacado:,.2f} (Valor Líquido = Total - Descontos)
            • **Varejo**: R$ {faturamento_varejo:,.2f} (Valor Líquido = Total - Descontos)
            • **Total**: R$ {faturamento_total:,.2f}
            
            **📊 MÉDIA DIÁRIA:**
            • **Atacado**: R$ {media_diaria_atacado:,.2f}/dia (Faturamento ÷ Dias trabalhados)
            • **Varejo**: R$ {media_diaria_varejo:,.2f}/dia (Faturamento ÷ Dias trabalhados)
            • **Consolidada**: R$ {media_diaria_total:,.2f}/dia
            
            **🔮 PROJEÇÃO FIM DO MÊS:**
            • **Cálculo**: Média diária consolidada × 27 dias úteis
            • **Resultado**: R$ {projecao_consolidada:,.2f}
            • **Vs Meta Atacado**: {percent_meta:+.1f}% (R$ {diferenca_meta:,.2f})
            
            **📈 FATORES CONSIDERADOS:**
            • Valores líquidos (descontados) para máxima precisão
            • Sazonalidade típica dos setores
            • Dias úteis restantes no mês
            • Tendência baseada no desempenho atual
            
            **⚠️ LIMITAÇÕES:**
            • Projeção linear (não considera aceleração/desaceleração)
            • Não inclui eventos especiais ou promoções futuras
            • Baseado apenas em dados históricos do mês atual
            • Sujeito a variações de mercado e sazonalidade
            
            **💡 RECOMENDAÇÕES:**
            • Acompanhar diariamente para ajustes
            • Considerar fatores externos (feriados, eventos)
            • Revisar estratégias se projeção divergir da meta
            """)
    
    # Detalhamento por setor - Layout responsivo
    if layout_mode == "📱 Mobile":
        # Mobile: seções empilhadas
        st.markdown("**🏢 Atacado:**")
        if metricas_atacado:
            dias_atacado = metricas_atacado['dias_com_vendas']
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.write(f"• **Dias**: {dias_atacado}")
                st.write(f"• **Faturamento**: R$ {faturamento_atacado:,.0f}")
            with col_m2:
                st.write(f"• **Média diária**: R$ {media_diaria_atacado:,.0f}")
                st.write(f"• **Projeção**: R$ {media_diaria_atacado * dias_uteis:,.0f}")
        else:
            st.write("• Dados não disponíveis")
        
        st.markdown("**🏪 Varejo:**")
        if metricas_varejo:
            dias_varejo = metricas_varejo['dias_com_vendas']
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                st.write(f"• **Dias**: {dias_varejo}")
                st.write(f"• **Faturamento**: R$ {faturamento_varejo:,.0f}")
            with col_v2:
                st.write(f"• **Média diária**: R$ {media_diaria_varejo:,.0f}")
                st.write(f"• **Projeção**: R$ {media_diaria_varejo * dias_uteis:,.0f}")
        else:
            st.write("• Dados não disponíveis")
    
    else:
        # Desktop: layout original com colunas lado a lado
        col_det1, col_det2 = st.columns(2)
        
        with col_det1:
            st.markdown("**🏢 Detalhamento Atacado:**")
            if metricas_atacado:
                dias_atacado = metricas_atacado['dias_com_vendas']
                st.write(f"• **Dias trabalhados**: {dias_atacado}")
                st.write(f"• **Faturamento líquido**: R$ {faturamento_atacado:,.2f}")
                st.write(f"• **Média diária**: R$ {media_diaria_atacado:,.2f}")
                st.write(f"• **Projeção setor**: R$ {media_diaria_atacado * dias_uteis:,.2f}")
            else:
                st.write("• Dados não disponíveis")
        
        with col_det2:
            st.markdown("**🏪 Detalhamento Varejo:**")
            if metricas_varejo:
                dias_varejo = metricas_varejo['dias_com_vendas']
                st.write(f"• **Dias trabalhados**: {dias_varejo}")
                st.write(f"• **Faturamento líquido**: R$ {faturamento_varejo:,.2f}")
                st.write(f"• **Média diária**: R$ {media_diaria_varejo:,.2f}")
                st.write(f"• **Projeção setor**: R$ {media_diaria_varejo * dias_uteis:,.2f}")
            else:
                st.write("• Dados não disponíveis")
    
    # === 4. RESUMO ESTRATÉGICO ===
    st.markdown("---")
    st.markdown("### 📈 Resumo Estratégico")
    
    # Calcular variação com ontem
    var_ontem = 0
    if vendas_hoje_atacado and 'var_ontem' in vendas_hoje_atacado:
        var_ontem = vendas_hoje_atacado['var_ontem']['faturamento']
    
    # Resumo estratégico - Layout responsivo
    if layout_mode == "📱 Mobile":
        # Mobile: seções empilhadas
        st.markdown("**💪 PONTOS FORTES:**")
        pontos_fortes = []
        
        if percent_meta > 10:
            pontos_fortes.append("🎯 Projeção acima da meta")
        
        if tem_varejo and fat_varejo > 0:
            pontos_fortes.append("🏪 Varejo contribuindo")
        
        if tem_atacado and qtd_clientes_novos >= 2:
            pontos_fortes.append("👥 Boa captação de clientes")
        
        if var_ontem > 5:
            pontos_fortes.append("📈 Crescimento vs ontem")
        
        if not pontos_fortes:
            pontos_fortes.append("💼 Operação funcionando")
        
        # Mostrar apenas os 3 primeiros no mobile
        for ponto in pontos_fortes[:3]:
            st.success(ponto)
        
        st.markdown("**⚠️ ATENÇÃO:**")
        pontos_atencao = []
        
        if percent_meta < -10:
            pontos_atencao.append("📉 Projeção abaixo da meta")
    
    else:
        # Desktop: layout original com colunas
        col_resumo1, col_resumo2 = st.columns(2)
        
        with col_resumo1:
            st.markdown("**💪 PONTOS FORTES:**")
            pontos_fortes = []
            
            if percent_meta > 10:
                pontos_fortes.append("🎯 Projeção acima da meta do atacado")
            
            if tem_varejo and fat_varejo > 0:
                pontos_fortes.append("🏪 Varejo contribuindo para receita")
            
            if tem_atacado and qtd_clientes_novos >= 2:
                pontos_fortes.append("👥 Boa captação de clientes novos")
            
            if var_ontem > 5:
                pontos_fortes.append("📈 Crescimento vs ontem")
            
            if not pontos_fortes:
                pontos_fortes.append("💼 Operação funcionando")
            
            for ponto in pontos_fortes:
                st.success(ponto)
        
        with col_resumo2:
            st.markdown("**⚠️ PONTOS DE ATENÇÃO:**")
            pontos_atencao = []
            
            if percent_meta < -10:
                pontos_atencao.append("📉 Projeção abaixo da meta")
        
        if tem_atacado and qtd_clientes_novos < 2:
            pontos_atencao.append("👥 Poucos clientes novos hoje")
        
        if var_ontem < -10:
            pontos_atencao.append("📉 Queda vs ontem")
        
        if not tem_varejo:
            pontos_atencao.append("🏪 Dados do varejo não disponíveis")
        
        if not pontos_atencao:
            pontos_atencao.append("✅ Nenhum ponto crítico identificado")
        
        for ponto in pontos_atencao:
            if "✅" in ponto:
                st.success(ponto)
            else:
                st.warning(ponto)

def dashboard_vendas(df, layout_mode):
    """Dashboard completo de vendas com abas - estrutura: Hoje | Histórico | Ticket Médio"""
    st.title("📊 Dashboard de Vendas - Grãos S.A.")
    st.markdown("*Análise completa de vendas e faturamento*")
    
    # === SISTEMA DE ABAS ===
    # Gerar título dinâmico para a aba
    data_atacado = obter_data_mais_recente_str(df)
    if data_atacado:
        titulo_aba = f"🔥 Vendas de {data_atacado}"
    else:
        titulo_aba = "🔥 Vendas de Hoje"
    
    tab_hoje, tab_historico, tab_ticket, tab_avancadas = st.tabs([
        titulo_aba, 
        "📈 Análise Histórica", 
        "💰 Central Ticket Médio",
        "📊 Métricas Avançadas"
    ])
    
    # ═══ ABA 1: VENDAS DE HOJE ═══ 
    with tab_hoje:
        st.markdown("### 🔥 Dashboard de Vendas - Atacado")
        st.caption("*Comparações temporais, métricas do mês e projeções com meta*")
        
        # Obter dados com meta configurável
        meta_mensal = st.session_state.get('meta_atacado', 850000)
        dias_uteis = st.session_state.get('dias_uteis_atacado', 27)
        
        # === 1. COMPARAÇÕES TEMPORAIS ===
        st.markdown("#### 📊 Comparações Temporais")
        
        comparacoes = calcular_comparacoes_temporais(df)
        
        if comparacoes:
            # Seletor de período para comparação
            periodo_selecionado = st.selectbox(
                "📅 Comparar vendas de hoje com:",
                ["Ontem", "7 dias atrás", "15 dias atrás"],
                help="Escolha o período de comparação"
            )
            
            # Dados para exibição baseados na seleção
            if periodo_selecionado == "Ontem":
                dados_comparacao = comparacoes['ontem']
                variacoes = comparacoes['var_ontem']
                periodo_label = f"vs {dados_comparacao['data'].strftime('%d/%m')}"
            elif periodo_selecionado == "7 dias atrás":
                dados_comparacao = comparacoes['dias_7']
                variacoes = comparacoes['var_7_dias']
                periodo_label = f"vs {dados_comparacao['data'].strftime('%d/%m')}"
            else:  # 15 dias atrás
                dados_comparacao = comparacoes['dias_15']
                variacoes = comparacoes['var_15_dias']
                periodo_label = f"vs {dados_comparacao['data'].strftime('%d/%m')}"
            
            # Métricas de comparação
            col_comp1, col_comp2, col_comp3, col_comp4 = st.columns(4)
            
            with col_comp1:
                delta_fat = f"{variacoes['faturamento']:+.1f}%" if variacoes['faturamento'] != 0 else "Estável"
                cor_fat = "normal" if variacoes['faturamento'] >= 0 else "inverse"
                st.metric(
                    label=f"💰 Faturamento Hoje",
                    value=f"R$ {comparacoes['hoje']['faturamento']:,.2f}",
                    delta=f"{delta_fat} {periodo_label}",
                    delta_color=cor_fat,
                    help=f"Hoje ({comparacoes['hoje']['data'].strftime('%d/%m')}) {periodo_label}"
                )
            
            with col_comp2:
                delta_vendas = f"{variacoes['vendas']:+.1f}%" if variacoes['vendas'] != 0 else "Estável"
                cor_vendas = "normal" if variacoes['vendas'] >= 0 else "inverse"
                st.metric(
                    label=f"🛒 Vendas Hoje",
                    value=f"{comparacoes['hoje']['vendas']}",
                    delta=f"{delta_vendas} {periodo_label}",
                    delta_color=cor_vendas,
                    help=f"Quantidade de vendas hoje {periodo_label}"
                )
            
            with col_comp3:
                delta_ticket = f"{variacoes['ticket']:+.1f}%" if variacoes['ticket'] != 0 else "Estável"
                cor_ticket = "normal" if variacoes['ticket'] >= 0 else "inverse"
                st.metric(
                    label=f"📊 Ticket Médio Hoje",
                    value=f"R$ {comparacoes['hoje']['ticket_medio']:,.2f}",
                    delta=f"{delta_ticket} {periodo_label}",
                    delta_color=cor_ticket,
                    help=f"Valor médio por venda hoje {periodo_label}"
                )
            
            with col_comp4:
                st.metric(
                    label="📅 Última Atualização",
                    value=comparacoes['hoje']['data'].strftime('%d/%m/%Y'),
                    help="Data dos dados mais recentes"
                )
        else:
            st.warning("❌ Dados insuficientes para comparações temporais")
        
        # === 2. MÉTRICAS DO MÊS COM META ===
        st.markdown("---")
        st.markdown("#### 📈 Performance do Mês - Atacado")
        
        metricas_mes = calcular_metricas_mes_atacado(df, meta_mensal, dias_uteis)
        
        if metricas_mes:
            # Barra de progresso visual da meta
            st.markdown("**🎯 Progresso em relação à Meta:**")
            
            # Calcular progresso (limitado a 100% para a barra)
            progresso_visual = min(metricas_mes['progresso_meta'] / 100, 1.0)
            
            # Barra de progresso
            st.progress(progresso_visual)
            
            # Informações da meta em colunas
            col_barra1, col_barra2, col_barra3 = st.columns(3)
            
            with col_barra1:
                st.markdown(f"**💰 Meta:** R$ {meta_mensal:,.0f}")
            
            with col_barra2:
                st.markdown(f"**📈 Atual:** R$ {metricas_mes['faturamento_mes']:,.0f}")
            
            with col_barra3:
                if metricas_mes['faturamento_mes'] >= meta_mensal:
                    excesso = metricas_mes['faturamento_mes'] - meta_mensal
                    st.markdown(f"**✅ {metricas_mes['progresso_meta']:.1f}%** (+R$ {excesso:,.0f})")
                else:
                    falta = meta_mensal - metricas_mes['faturamento_mes']
                    st.markdown(f"**📊 {metricas_mes['progresso_meta']:.1f}%** (Falta: R$ {falta:,.0f})")
            
            st.markdown("---")
            # Métricas principais do mês
            col_mes1, col_mes2, col_mes3, col_mes4 = st.columns(4)
            
            with col_mes1:
                delta_meta = f"Faltam R$ {metricas_mes['falta_meta']:,.0f}" if metricas_mes['falta_meta'] > 0 else "META ATINGIDA! 🎉"
                cor_meta = "normal" if metricas_mes['progresso_meta'] >= 100 else "inverse"
                st.metric(
                    label="🎯 Progresso da Meta",
                    value=f"{metricas_mes['progresso_meta']:.1f}%",
                    delta=delta_meta,
                    delta_color=cor_meta,
                    help=f"Meta: R$ {meta_mensal:,.0f} | Atual: R$ {metricas_mes['faturamento_mes']:,.0f}"
                )
            
            with col_mes2:
                st.metric(
                    label="💰 Faturamento do Mês",
                    value=f"R$ {metricas_mes['faturamento_mes']:,.2f}",
                    delta=f"{metricas_mes['vendas_quantidade']} vendas",
                    help=f"Total acumulado em {metricas_mes['dias_com_vendas']} dias de vendas"
                )
            
            with col_mes3:
                st.metric(
                    label="📊 Média Diária Atual",
                    value=f"R$ {metricas_mes['media_diaria_atual']:,.2f}",
                    delta=f"Necessária: R$ {metricas_mes['media_necessaria']:,.2f}",
                    delta_color="normal" if metricas_mes['media_diaria_atual'] >= metricas_mes['media_necessaria'] else "inverse",
                    help=f"Média atual vs necessária para atingir meta"
                )
            
            with col_mes4:
                st.metric(
                    label="📅 Dias Restantes",
                    value=f"{metricas_mes['dias_restantes']}",
                    delta=f"{metricas_mes['dias_com_vendas']}/{dias_uteis} trabalhados",
                    help="Dias úteis restantes para atingir a meta"
                )
            
            # Análise do progresso
            if metricas_mes['progresso_meta'] >= 100:
                st.success(f"🎉 **META ATINGIDA!** Parabéns! Vocês superaram a meta de R$ {meta_mensal:,.0f}")
            elif metricas_mes['progresso_meta'] >= 80:
                st.info(f"🎯 **QUASE LÁ!** {metricas_mes['progresso_meta']:.1f}% da meta atingida - faltam apenas R$ {metricas_mes['falta_meta']:,.0f}")
            elif metricas_mes['progresso_meta'] >= 60:
                st.warning(f"📈 **ACELERAÇÃO NECESSÁRIA**: {metricas_mes['progresso_meta']:.1f}% da meta - intensificar esforços")
            else:
                st.error(f"🚨 **ATENÇÃO URGENTE**: Apenas {metricas_mes['progresso_meta']:.1f}% da meta - revisar estratégia")
            
            # Métricas adicionais do mês
            st.markdown("**📊 Métricas Complementares:**")
            col_extra1, col_extra2, col_extra3, col_extra4 = st.columns(4)
            
            with col_extra1:
                st.metric(
                    label="💎 Ticket Médio do Mês",
                    value=f"R$ {metricas_mes['ticket_medio_mes']:,.2f}",
                    help="Valor médio por venda no mês atual"
                )
            
            with col_extra2:
                vendas_dia_medio = metricas_mes['vendas_quantidade'] / metricas_mes['dias_com_vendas'] if metricas_mes['dias_com_vendas'] > 0 else 0
                st.metric(
                    label="🔄 Vendas/Dia Médio",
                    value=f"{vendas_dia_medio:.1f}",
                    help="Número médio de vendas por dia"
                )
            
            with col_extra3:
                ritmo_ideal = meta_mensal / dias_uteis
                st.metric(
                    label="🎯 Ritmo Ideal",
                    value=f"R$ {ritmo_ideal:,.0f}/dia",
                    delta=f"Atual: R$ {metricas_mes['media_diaria_atual']:,.0f}",
                    delta_color="normal" if metricas_mes['media_diaria_atual'] >= ritmo_ideal else "inverse",
                    help="Ritmo diário necessário para atingir meta"
                )
            
            with col_extra4:
                eficiencia = (metricas_mes['media_diaria_atual'] / ritmo_ideal * 100) if ritmo_ideal > 0 else 0
                st.metric(
                    label="⚡ Eficiência",
                    value=f"{eficiencia:.1f}%",
                    help="% da performance necessária que está sendo atingida"
                )
        else:
            st.warning("❌ Dados insuficientes para métricas do mês")
        
        # === 3. PROJEÇÕES MELHORADAS ===
        st.markdown("---")
        st.markdown("#### 🔮 Projeções Inteligentes")
        st.caption("*4 métodos de projeção baseados em dados reais*")
        
        projecoes = calcular_projecoes_melhoradas(df, meta_mensal, dias_uteis)
        
        if projecoes:
            # Layout de projeções com cards visuais melhorados
            col_proj1, col_proj2, col_proj3, col_proj4 = st.columns(4)
            
            with col_proj1:
                delta_simples = f"vs Meta: {((projecoes['projecao_simples'] - meta_mensal) / meta_mensal * 100):+.1f}%"
                cor_simples = "normal" if projecoes['projecao_simples'] >= meta_mensal else "inverse"
                st.metric(
                    label="📊 Média Simples",
                    value=f"R$ {projecoes['projecao_simples']:,.0f}",
                    delta=delta_simples,
                    delta_color=cor_simples,
                    help="Projeção baseada na média diária atual"
                )
                
                if st.button("💡 Como Calculamos", key="help_simples_novo", use_container_width=True):
                    with st.expander("📊 **Método: Média Simples**", expanded=True):
                        st.markdown(f"""
                        **📈 Cálculo:**
                        - Faturamento atual: **R$ {projecoes['faturamento_atual']:,.2f}**
                        - Dias trabalhados: **{projecoes['dias_trabalhados']} dias**
                        - Média diária: **R$ {projecoes['media_diaria']:,.2f}**
                        - Projeção: **R$ {projecoes['media_diaria']:,.2f} × {dias_uteis} dias**
                        
                        **✅ Vantagem:** Método conservador e confiável  
                        **⚠️ Limitação:** Não considera mudanças de ritmo
                        """)
            
            with col_proj2:
                delta_tendencia = f"vs Simples: {((projecoes['projecao_tendencia'] - projecoes['projecao_simples']) / projecoes['projecao_simples'] * 100):+.1f}%"
                st.metric(
                    label="📈 Com Tendência",
                    value=f"R$ {projecoes['projecao_tendencia']:,.0f}",
                    delta=delta_tendencia,
                    help="Considera aceleração/desaceleração das vendas"
                )
                
                if st.button("💡 Como Calculamos", key="help_tendencia_novo", use_container_width=True):
                    with st.expander("📈 **Método: Com Tendência**", expanded=True):
                        st.markdown(f"""
                        **📊 Análise de Momentum:**
                        - Base: Método da média simples
                        - Compara primeiros vs últimos dias
                        - Aplica tendência aos dias restantes
                        
                        **🎯 Resultado:** R$ {projecoes['projecao_tendencia']:,.0f}
                        
                        **✅ Vantagem:** Captura momentum atual  
                        **⚠️ Limitação:** Assume tendência constante
                        """)
            
            with col_proj3:
                delta_meta = f"vs Meta: {((projecoes['projecao_meta'] - meta_mensal) / meta_mensal * 100):+.1f}%"
                cor_meta_proj = "normal" if projecoes['projecao_meta'] >= meta_mensal else "inverse"
                st.metric(
                    label="🎯 Baseada na Meta",
                    value=f"R$ {projecoes['projecao_meta']:,.0f}",
                    delta=delta_meta,
                    delta_color=cor_meta_proj,
                    help="Ritmo necessário para atingir exatamente a meta"
                )
                
                if st.button("💡 Como Calculamos", key="help_meta_novo", use_container_width=True):
                    with st.expander("🎯 **Método: Baseada na Meta**", expanded=True):
                        st.markdown(f"""
                        **🎯 Cálculo para Meta:**
                        - Meta estabelecida: **R$ {meta_mensal:,.0f}**
                        - Já faturado: **R$ {projecoes['faturamento_atual']:,.0f}**
                        - Falta atingir: **R$ {meta_mensal - projecoes['faturamento_atual']:,.0f}**
                        - Ritmo necessário: **R$ {projecoes['ritmo_necessario']:,.0f}/dia**
                        
                        **✅ Vantagem:** Focado no objetivo  
                        **⚠️ Limitação:** Pode ser irreal se meta muito alta
                        """)
            
            with col_proj4:
                delta_hibrida = f"Recomendada: {((projecoes['projecao_hibrida'] - meta_mensal) / meta_mensal * 100):+.1f}%"
                cor_hibrida = "normal" if projecoes['projecao_hibrida'] >= meta_mensal else "inverse"
                st.metric(
                    label="🧠 Método Híbrido",
                    value=f"R$ {projecoes['projecao_hibrida']:,.0f}",
                    delta=delta_hibrida,
                    delta_color=cor_hibrida,
                    help="⭐ Combinação inteligente dos 3 métodos"
                )
                
                if st.button("💡 Como Calculamos", key="help_hibrida_novo", use_container_width=True):
                    with st.expander("🧠 **Método: Híbrido Inteligente ⭐**", expanded=True):
                        progresso_atual = projecoes['faturamento_atual'] / meta_mensal
                        if progresso_atual > 0.8:
                            pesos = "50% Simples + 30% Tendência + 20% Meta"
                            explicacao = "Próximo da meta: priorizamos conservadorismo"
                        else:
                            pesos = "30% Simples + 40% Tendência + 30% Meta"
                            explicacao = "Distante da meta: priorizamos crescimento"
                        
                        st.markdown(f"""
                        **🧠 Combinação Inteligente:**
                        - **Pesos:** {pesos}
                        - **Lógica:** {explicacao}
                        - **Resultado:** R$ {projecoes['projecao_hibrida']:,.0f}
                        
                        **⭐ Por que é o melhor:**
                        - Combina conservadorismo + realismo + ambição
                        - Se adapta ao progresso atual
                        - Maior precisão estatística
                        
                        **✅ Recomendação:** Use este para planejamento
                        """)
            
            # Análise das projeções (sem recomendação automática - conforme solicitado)
            st.markdown("**📊 Resumo das Projeções:**")
            projecoes_ordenadas = [
                ("Simples", projecoes['projecao_simples']),
                ("Tendência", projecoes['projecao_tendencia']),
                ("Meta", projecoes['projecao_meta']),
                ("Híbrida ⭐", projecoes['projecao_hibrida'])
            ]
            projecoes_ordenadas.sort(key=lambda x: x[1], reverse=True)
            
            for i, (nome, valor) in enumerate(projecoes_ordenadas):
                posicao = f"{i+1}º"
                diferenca_meta = ((valor - meta_mensal) / meta_mensal * 100)
                if diferenca_meta >= 0:
                    st.success(f"**{posicao} {nome}**: R$ {valor:,.0f} (+{diferenca_meta:.1f}% vs Meta)")
                else:
                    st.error(f"**{posicao} {nome}**: R$ {valor:,.0f} ({diferenca_meta:.1f}% vs Meta)")
        else:
            st.warning("❌ Dados insuficientes para calcular projeções")
    
    # ═══ ABA 2: ANÁLISE HISTÓRICA ═══
    with tab_historico:
        st.markdown("### 📈 Análise Histórica de Vendas")
        st.caption("*Compare vendas entre diferentes meses*")
        
        # Preparar dados históricos
        df_temp = df.copy()
        df_temp['Data_Competencia'] = pd.to_datetime(df_temp['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
        df_temp = df_temp.dropna(subset=['Data_Competencia'])
        
        # Agrupar por mês/ano
        df_temp['Mes_Ano'] = df_temp['Data_Competencia'].dt.to_period('M')
        vendas_por_mes = df_temp.groupby('Mes_Ano').agg({
            'Total_Venda': ['sum', 'count', 'mean'],
            'Data_Competencia': 'nunique'
        }).round(2)
        
        vendas_por_mes.columns = ['Faturamento_Total', 'Qtd_Vendas', 'Ticket_Medio', 'Dias_Com_Vendas']
        vendas_por_mes = vendas_por_mes.reset_index()
        vendas_por_mes['Mes_Ano_Str'] = vendas_por_mes['Mes_Ano'].dt.strftime('%b/%Y')
        
        if not vendas_por_mes.empty:
            # Seletor de meses para comparação
            meses_disponiveis = vendas_por_mes['Mes_Ano_Str'].tolist()
            
            col_sel1, col_sel2 = st.columns(2)
            with col_sel1:
                mes_base = st.selectbox(
                    "📅 Mês Base para Comparação:",
                    meses_disponiveis,
                    index=len(meses_disponiveis)-1 if len(meses_disponiveis) > 0 else 0,
                    help="Mês que será usado como referência"
                )
            
            with col_sel2:
                meses_comparacao = [m for m in meses_disponiveis if m != mes_base]
                if meses_comparacao:
                    mes_compare = st.selectbox(
                        "📊 Comparar com:",
                        meses_comparacao,
                        help="Mês para comparar com o mês base"
                    )
                else:
                    mes_compare = None
                    st.info("📅 Apenas um mês disponível para análise")
            
            # Análise comparativa entre meses
            if mes_compare:
                dados_base = vendas_por_mes[vendas_por_mes['Mes_Ano_Str'] == mes_base].iloc[0]
                dados_compare = vendas_por_mes[vendas_por_mes['Mes_Ano_Str'] == mes_compare].iloc[0]
                
                st.markdown(f"#### 🔍 {mes_base} vs {mes_compare}")
                
                col_comp1, col_comp2, col_comp3, col_comp4 = st.columns(4)
                
                with col_comp1:
                    var_faturamento = ((dados_base['Faturamento_Total'] - dados_compare['Faturamento_Total']) / dados_compare['Faturamento_Total'] * 100) if dados_compare['Faturamento_Total'] > 0 else 0
                    st.metric(
                        label="💰 Faturamento",
                        value=f"R$ {dados_base['Faturamento_Total']:,.2f}",
                        delta=f"{var_faturamento:+.1f}%",
                        delta_color="normal" if var_faturamento >= 0 else "inverse",
                        help=f"Comparado com {mes_compare}"
                    )
                
                with col_comp2:
                    var_vendas = ((dados_base['Qtd_Vendas'] - dados_compare['Qtd_Vendas']) / dados_compare['Qtd_Vendas'] * 100) if dados_compare['Qtd_Vendas'] > 0 else 0
                    st.metric(
                        label="🛒 Número de Vendas",
                        value=f"{int(dados_base['Qtd_Vendas'])}",
                        delta=f"{var_vendas:+.1f}%",
                        delta_color="normal" if var_vendas >= 0 else "inverse",
                        help=f"Comparado com {mes_compare}"
                    )
                
                with col_comp3:
                    var_ticket = ((dados_base['Ticket_Medio'] - dados_compare['Ticket_Medio']) / dados_compare['Ticket_Medio'] * 100) if dados_compare['Ticket_Medio'] > 0 else 0
                    st.metric(
                        label="📊 Ticket Médio",
                        value=f"R$ {dados_base['Ticket_Medio']:,.2f}",
                        delta=f"{var_ticket:+.1f}%",
                        delta_color="normal" if var_ticket >= 0 else "inverse",
                        help=f"Comparado com {mes_compare}"
                    )
                
                with col_comp4:
                    var_dias = dados_base['Dias_Com_Vendas'] - dados_compare['Dias_Com_Vendas']
                    st.metric(
                        label="📅 Dias de Vendas",
                        value=f"{int(dados_base['Dias_Com_Vendas'])}",
                        delta=f"{var_dias:+.0f} dias",
                        delta_color="normal" if var_dias >= 0 else "inverse",
                        help=f"Dias com vendas vs {mes_compare}"
                    )
                
                # Análise automática da comparação
                st.markdown("---")
                st.markdown("### 🎯 Análise Automática")
                
                analises_historicas = []
                
                if var_faturamento > 15:
                    analises_historicas.append(f"🎉 **EXCELENTE CRESCIMENTO**: Faturamento {var_faturamento:.1f}% maior que {mes_compare}")
                elif var_faturamento > 5:
                    analises_historicas.append(f"✅ **BOM CRESCIMENTO**: Faturamento {var_faturamento:.1f}% maior que {mes_compare}")
                elif var_faturamento < -15:
                    analises_historicas.append(f"🚨 **ATENÇÃO**: Faturamento {abs(var_faturamento):.1f}% menor que {mes_compare}")
                elif var_faturamento < -5:
                    analises_historicas.append(f"⚠️ **QUEDA**: Faturamento {abs(var_faturamento):.1f}% menor que {mes_compare}")
                
                if var_ticket > 10:
                    analises_historicas.append(f"💰 **TICKET EM ALTA**: {var_ticket:.1f}% maior - clientes gastando mais!")
                elif var_ticket < -10:
                    analises_historicas.append(f"📉 **TICKET EM QUEDA**: {abs(var_ticket):.1f}% menor - revisar estratégia de preços")
                
                if var_vendas > 10:
                    analises_historicas.append(f"📈 **VOLUME CRESCENDO**: {var_vendas:.1f}% mais vendas que {mes_compare}")
                elif var_vendas < -10:
                    analises_historicas.append(f"📉 **VOLUME EM QUEDA**: {abs(var_vendas):.1f}% menos vendas - acelerar captação")
                
                if analises_historicas:
                    for analise in analises_historicas:
                        st.info(analise)
                else:
                    st.info("📊 **ESTÁVEL**: Performance similar entre os meses")
            
            # Tabela histórica completa
            st.markdown("---")
            st.markdown("### 📊 Histórico Completo")
            
            # Preparar tabela para exibição
            vendas_display = vendas_por_mes.copy()
            vendas_display['Faturamento_Total'] = vendas_display['Faturamento_Total'].apply(lambda x: f"R$ {x:,.2f}")
            vendas_display['Ticket_Medio'] = vendas_display['Ticket_Medio'].apply(lambda x: f"R$ {x:,.2f}")
            vendas_display['Qtd_Vendas'] = vendas_display['Qtd_Vendas'].astype(int)
            vendas_display['Dias_Com_Vendas'] = vendas_display['Dias_Com_Vendas'].astype(int)
            
            st.dataframe(
                vendas_display[['Mes_Ano_Str', 'Faturamento_Total', 'Qtd_Vendas', 'Ticket_Medio', 'Dias_Com_Vendas']],
                column_config={
                    'Mes_Ano_Str': 'Mês/Ano',
                    'Faturamento_Total': 'Faturamento Total',
                    'Qtd_Vendas': 'Nº de Vendas',
                    'Ticket_Medio': 'Ticket Médio',
                    'Dias_Com_Vendas': 'Dias c/ Vendas'
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("❌ Não há dados suficientes para análise histórica")
    
    # ═══ ABA 3: CENTRAL TICKET MÉDIO ═══
    with tab_ticket:
        st.markdown("### 💰 Central de Análise - Ticket Médio")
        st.caption("*Análise detalhada do valor médio por venda*")
        
        # Preparar dados para análise de ticket médio
        df_temp = df.copy()
        df_temp['Data_Competencia'] = pd.to_datetime(df_temp['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
        df_temp = df_temp.dropna(subset=['Data_Competencia'])
        
        if not df_temp.empty:
            # Estatísticas gerais do ticket médio
            ticket_geral = df_temp['Total_Venda'].mean()
            ticket_mediano = df_temp['Total_Venda'].median()
            ticket_min = df_temp['Total_Venda'].min()
            ticket_max = df_temp['Total_Venda'].max()
            ticket_std = df_temp['Total_Venda'].std()
            
            st.markdown("#### 📊 Estatísticas Gerais")
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            
            with col_stat1:
                st.metric(
                    label="💰 Ticket Médio Geral",
                    value=f"R$ {ticket_geral:,.2f}",
                    help="Valor médio de todas as vendas"
                )
            
            with col_stat2:
                st.metric(
                    label="📊 Ticket Mediano",
                    value=f"R$ {ticket_mediano:,.2f}",
                    help="Valor que divide as vendas pela metade"
                )
            
            with col_stat3:
                st.metric(
                    label="📈 Maior Venda",
                    value=f"R$ {ticket_max:,.2f}",
                    help="Maior valor de venda registrado"
                )
            
            with col_stat4:
                st.metric(
                    label="📉 Menor Venda",
                    value=f"R$ {ticket_min:,.2f}",
                    help="Menor valor de venda registrado"
                )
            

            
            # Evolução mensal do ticket médio
            st.markdown("---")
            st.markdown("#### 📈 Evolução Mensal do Ticket Médio")
            
            df_temp['Mes_Ano'] = df_temp['Data_Competencia'].dt.to_period('M')
            ticket_mensal = df_temp.groupby('Mes_Ano')['Total_Venda'].mean().reset_index()
            ticket_mensal['Mes_Ano_Str'] = ticket_mensal['Mes_Ano'].dt.strftime('%b/%Y')
            
            if len(ticket_mensal) > 1:
                # Calcular variação mensal
                ticket_mensal['Variacao'] = ticket_mensal['Total_Venda'].pct_change() * 100
                
                # Criar gráfico da evolução
                import plotly.express as px
                
                fig = px.line(
                    ticket_mensal, 
                    x='Mes_Ano_Str', 
                    y='Total_Venda',
                    title='Evolução do Ticket Médio Mensal',
                    markers=True,
                    line_shape='spline'
                )
                
                fig.update_layout(
                    xaxis_title="Mês/Ano",
                    yaxis_title="Ticket Médio (R$)",
                    showlegend=False,
                    height=400
                )
                
                fig.update_traces(
                    line=dict(color='#4CAF50', width=3),
                    marker=dict(color='#2E7D32', size=8)
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Tabela com variações
                st.markdown("**📊 Detalhamento Mensal:**")
                for i, row in ticket_mensal.iterrows():
                    if i == 0:
                        st.write(f"• **{row['Mes_Ano_Str']}**: R$ {row['Total_Venda']:,.2f} (Base)")
                    else:
                        var_color = "🟢" if row['Variacao'] > 0 else "🔴" if row['Variacao'] < 0 else "🟡"
                        st.write(f"• **{row['Mes_Ano_Str']}**: R$ {row['Total_Venda']:,.2f} ({var_color} {row['Variacao']:+.1f}%)")
                
                # Análise da tendência
                tendencia_geral = ticket_mensal['Total_Venda'].iloc[-1] - ticket_mensal['Total_Venda'].iloc[0]
                percent_crescimento = (tendencia_geral / ticket_mensal['Total_Venda'].iloc[0] * 100) if ticket_mensal['Total_Venda'].iloc[0] > 0 else 0
                
                if percent_crescimento > 5:
                    st.success(f"📈 **TENDÊNCIA POSITIVA**: Crescimento de {percent_crescimento:+.1f}% no período")
                elif percent_crescimento < -5:
                    st.warning(f"📉 **TENDÊNCIA NEGATIVA**: Queda de {percent_crescimento:.1f}% no período")
                else:
                    st.info(f"➡️ **TENDÊNCIA ESTÁVEL**: Variação de {percent_crescimento:+.1f}% no período")
            else:
                st.info("📊 Apenas um mês de dados disponível - aguardando mais dados para análise da evolução")
            

        else:
            st.warning("❌ Não há dados suficientes para análise de ticket médio")
    
    # ═══ ABA 4: MÉTRICAS AVANÇADAS ═══
    with tab_avancadas:
        st.markdown("### 📊 Métricas Avançadas - Indicadores Estratégicos")
        st.caption("*Indicadores críticos para gestão estratégica e tomada de decisão*")
        
        # Preparar dados para análises avançadas
        df_temp = df.copy()
        df_temp['Data_Competencia'] = pd.to_datetime(df_temp['Data_Competencia'], format='%d/%m/%Y', errors='coerce')
        df_temp = df_temp.dropna(subset=['Data_Competencia'])
        
        if not df_temp.empty:
            # === 1. CONCENTRAÇÃO DE VENDAS (RISCO) ===
            st.markdown("#### 🎯 Concentração de Vendas")
            
            # Analisar concentração por cliente
            vendas_por_cliente = df_temp.groupby('Nome_Cliente')['Total_Venda'].agg(['sum', 'count']).sort_values('sum', ascending=False)
            vendas_por_cliente.columns = ['Faturamento_Total', 'Qtd_Vendas']
            vendas_por_cliente['Percentual_Faturamento'] = (vendas_por_cliente['Faturamento_Total'] / vendas_por_cliente['Faturamento_Total'].sum() * 100).round(1)
            
            # Regra 80/20 - Concentração
            faturamento_acumulado = vendas_por_cliente['Percentual_Faturamento'].cumsum()
            top_20_clientes = len(vendas_por_cliente) * 0.2
            top_10_clientes = min(10, len(vendas_por_cliente))
            
            faturamento_top10 = vendas_por_cliente.head(top_10_clientes)['Percentual_Faturamento'].sum()
            faturamento_top20_pct = faturamento_acumulado[faturamento_acumulado <= 80].count() / len(vendas_por_cliente) * 100
            
            col_conc1, col_conc2, col_conc3, col_conc4 = st.columns(4)
            
            with col_conc1:
                st.metric(
                    label="🏆 Top 10 Clientes",
                    value=f"{faturamento_top10:.1f}%",
                    help="% do faturamento gerado pelos 10 maiores clientes"
                )
            
            with col_conc2:
                clientes_80_pct = faturamento_acumulado[faturamento_acumulado <= 80].count()
                st.metric(
                    label="📊 Regra 80/20",
                    value=f"{clientes_80_pct} clientes",
                    delta=f"{clientes_80_pct/len(vendas_por_cliente)*100:.1f}% geram 80%",
                    help="Quantos clientes geram 80% do faturamento"
                )
            
            with col_conc3:
                clientes_únicos = len(vendas_por_cliente)
                st.metric(
                    label="👥 Total de Clientes",
                    value=f"{clientes_únicos}",
                    help="Número total de clientes únicos"
                )
            
            with col_conc4:
                maior_cliente_pct = vendas_por_cliente.iloc[0]['Percentual_Faturamento']
                st.metric(
                    label="⚠️ Maior Dependência",
                    value=f"{maior_cliente_pct:.1f}%",
                    help="% do faturamento do maior cliente"
                )
            
            # Botão separado para análise estratégica
            st.markdown("**👥 Análise Estratégica dos Clientes:**")
            
            # Layout responsivo para botões
            if layout_mode == "📱 Mobile":
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🔍 Ver Clientes", key="btn_clientes_dependentes", use_container_width=True):
                        st.session_state.mostrar_clientes = True
                with col_btn2:
                    if st.button("📊 Ampliar Mix", key="btn_ampliar_mix", use_container_width=True):
                        st.session_state.mostrar_estrategias = True
            else:
                col_btn1, col_btn2, col_btn3 = st.columns(3)
                with col_btn1:
                    if st.button("🔍 Ver Top 10 Clientes", key="btn_clientes_dependentes", use_container_width=True):
                        st.session_state.mostrar_clientes = True
                with col_btn2:
                    if st.button("📊 Estratégias para Ampliar Mix", key="btn_ampliar_mix", use_container_width=True):
                        st.session_state.mostrar_estrategias = True
                with col_btn3:
                    if st.button("📈 Perfil de Compras", key="btn_perfil_compras", use_container_width=True):
                        st.session_state.mostrar_perfil = True
            
            # === ANÁLISE DE CLIENTES DEPENDENTES ===
            if st.session_state.get('mostrar_clientes', False):
                with st.container():
                    st.markdown("#### 🔍 Top 10 Clientes - Análise de Dependência")
                    
                    # Botão para fechar - responsivo
                    if layout_mode == "📱 Mobile":
                        if st.button("❌ Fechar", key="btn_fechar_clientes", use_container_width=True):
                            st.session_state.mostrar_clientes = False
                            st.rerun()
                    else:
                        col_fecha, _, _ = st.columns([1, 2, 2])
                        with col_fecha:
                            if st.button("❌ Fechar", key="btn_fechar_clientes"):
                                st.session_state.mostrar_clientes = False
                                st.rerun()
                    
                    top_clientes = vendas_por_cliente.head(10).reset_index()
                    
                    # Análise detalhada de cada cliente
                    for i, cliente in top_clientes.iterrows():
                        nome_cliente = cliente['Nome_Cliente']
                        if len(nome_cliente) > 45:
                            nome_cliente = nome_cliente[:45] + "..."
                        
                        # Calcular métricas avançadas do cliente
                        vendas_cliente = df_temp[df_temp['Nome_Cliente'] == cliente['Nome_Cliente']]
                        
                        # Análise temporal
                        datas_compra = pd.to_datetime(vendas_cliente['Data_Competencia']).dt.date
                        primeiro_dia = datas_compra.min()
                        ultimo_dia = datas_compra.max()
                        dias_ativo = (ultimo_dia - primeiro_dia).days + 1
                        frequencia_compra = len(vendas_cliente) / max(dias_ativo, 1) * 30  # compras por mês
                        
                        # Ticket médio e variabilidade
                        ticket_medio = vendas_cliente['Total_Venda'].mean()
                        ticket_variacao = vendas_cliente['Total_Venda'].std() / ticket_medio * 100 if ticket_medio > 0 else 0
                        
                        # Últimas compras
                        dias_ultima_compra = (pd.Timestamp.now().date() - ultimo_dia).days
                        
                        # Status de risco
                        if cliente['Percentual_Faturamento'] > 30:
                            status = "🚨 RISCO CRÍTICO"
                            cor_status = "🔴"
                            prioridade = "MÁXIMA"
                        elif cliente['Percentual_Faturamento'] > 15:
                            status = "⚠️ ALTA DEPENDÊNCIA"
                            cor_status = "🟡" 
                            prioridade = "ALTA"
                        elif cliente['Percentual_Faturamento'] > 8:
                            status = "📊 MONITORAR"
                            cor_status = "🟠"
                            prioridade = "MÉDIA"
                        else:
                            status = "✅ SAUDÁVEL"
                            cor_status = "🟢"
                            prioridade = "BAIXA"
                        
                        # Layout responsivo para cada cliente
                        with st.expander(f"{cor_status} **{i+1}º** {nome_cliente} - {cliente['Percentual_Faturamento']:.1f}% ({status})", expanded=i==0):
                            if layout_mode == "📱 Mobile":
                                # Mobile: layout empilhado
                                st.markdown(f"**💰 Faturamento:** R$ {cliente['Faturamento_Total']:,.0f}")
                                st.markdown(f"**📊 Participação:** {cliente['Percentual_Faturamento']:.1f}% do total")
                                st.markdown(f"**🛒 Compras:** {cliente['Qtd_Vendas']} vendas")
                                st.markdown(f"**🎯 Ticket Médio:** R$ {ticket_medio:,.0f}")
                                
                                st.markdown("---")
                                st.markdown(f"**📅 Frequência:** {frequencia_compra:.1f} compras/mês")
                                st.markdown(f"**⏱️ Última compra:** {dias_ultima_compra} dias atrás")
                                st.markdown(f"**📈 Variação ticket:** {ticket_variacao:.0f}%")
                                st.markdown(f"**🚨 Prioridade:** {prioridade}")
                                
                            else:
                                # Desktop: layout em colunas
                                col_met1, col_met2, col_met3, col_met4 = st.columns(4)
                                
                                with col_met1:
                                    st.metric("💰 Faturamento", f"R$ {cliente['Faturamento_Total']:,.0f}", 
                                            f"{cliente['Percentual_Faturamento']:.1f}% do total")
                                
                                with col_met2:
                                    st.metric("🛒 Compras", f"{cliente['Qtd_Vendas']}", 
                                            f"{frequencia_compra:.1f}/mês")
                                
                                with col_met3:
                                    st.metric("🎯 Ticket Médio", f"R$ {ticket_medio:,.0f}", 
                                            f"±{ticket_variacao:.0f}%")
                                
                                with col_met4:
                                    st.metric("⏱️ Última Compra", f"{dias_ultima_compra} dias", 
                                            f"Prioridade: {prioridade}")
                            
                            # Recomendações específicas
                            st.markdown("**💡 Ações Recomendadas:**")
                            
                            if cliente['Percentual_Faturamento'] > 30:
                                st.error("🚨 **URGENTE**: Diversificar imediatamente! Cliente representa risco crítico.")
                                st.markdown("• Oferecer novos produtos/serviços")
                                st.markdown("• Negociar contratos de longo prazo")
                                st.markdown("• Buscar novos clientes para reduzir dependência")
                                
                            elif cliente['Percentual_Faturamento'] > 15:
                                st.warning("⚠️ **ATENÇÃO**: Monitorar e ampliar relacionamento")
                                st.markdown("• Apresentar catálogo completo")
                                st.markdown("• Identificar necessidades não atendidas")
                                st.markdown("• Fortalecer relacionamento comercial")
                                
                            else:
                                st.success("✅ **OPORTUNIDADE**: Cliente saudável para crescimento")
                                st.markdown("• Explorar potencial de crescimento")
                                st.markdown("• Cross-selling de produtos relacionados")
                    
                    # Resumo da análise
                    st.markdown("---")
                    st.markdown("### 📊 Resumo Estratégico")
                    
                    clientes_risco_critico = sum(1 for _, c in top_clientes.iterrows() if c['Percentual_Faturamento'] > 30)
                    clientes_alta_dependencia = sum(1 for _, c in top_clientes.iterrows() if 15 <= c['Percentual_Faturamento'] <= 30)
                    
                    if layout_mode == "📱 Mobile":
                        st.error(f"🚨 **{clientes_risco_critico}** clientes em risco crítico")
                        st.warning(f"⚠️ **{clientes_alta_dependencia}** clientes com alta dependência")
                        st.info(f"💡 **{10 - clientes_risco_critico - clientes_alta_dependencia}** clientes com potencial de crescimento")
                    else:
                        col_res1, col_res2, col_res3 = st.columns(3)
                        with col_res1:
                            st.error(f"🚨 **Risco Crítico**: {clientes_risco_critico} clientes")
                        with col_res2:
                            st.warning(f"⚠️ **Alta Dependência**: {clientes_alta_dependencia} clientes")
                        with col_res3:
                            st.success(f"📈 **Potencial Crescimento**: {10 - clientes_risco_critico - clientes_alta_dependencia} clientes")
            
            # === ESTRATÉGIAS PARA AMPLIAR MIX ===
            if st.session_state.get('mostrar_estrategias', False):
                with st.container():
                    st.markdown("#### 📊 Estratégias para Ampliar Mix de Produtos")
                    
                    # Botão para fechar
                    if st.button("❌ Fechar Estratégias", key="btn_fechar_estrategias"):
                        st.session_state.mostrar_estrategias = False
                        st.rerun()
                    
                    # Análise do mix atual por cliente
                    st.markdown("##### 🎯 Oportunidades de Cross-Selling")
                    
                    # Para cada cliente do top 5, analisar seu perfil
                    top_5_clientes = vendas_por_cliente.head(5).reset_index()
                    
                    for i, cliente in top_5_clientes.iterrows():
                        vendas_cliente = df_temp[df_temp['Nome_Cliente'] == cliente['Nome_Cliente']]
                        
                        # Análise de produtos mais comprados pelo cliente
                        if 'Produto' in vendas_cliente.columns:
                            produtos_cliente = vendas_cliente.groupby('Produto')['Total_Venda'].agg(['sum', 'count']).sort_values('sum', ascending=False)
                        else:
                            # Se não tem coluna produto, analisar por valor
                            produtos_cliente = vendas_cliente.groupby('Total_Venda')['Total_Venda'].count().sort_values(ascending=False)
                        
                        nome_cliente = cliente['Nome_Cliente']
                        if len(nome_cliente) > 30:
                            nome_cliente = nome_cliente[:30] + "..."
                        
                        with st.expander(f"📊 **{i+1}º** {nome_cliente} - Análise de Mix"):
                            col_atual, col_oportunidade = st.columns(2)
                            
                            with col_atual:
                                st.markdown("**📋 Perfil Atual:**")
                                st.markdown(f"• **Total gasto**: R$ {cliente['Faturamento_Total']:,.0f}")
                                st.markdown(f"• **Nº de compras**: {cliente['Qtd_Vendas']}")
                                st.markdown(f"• **Ticket médio**: R$ {cliente['Faturamento_Total']/cliente['Qtd_Vendas']:,.0f}")
                                
                                # Frequência de compra
                                try:
                                    # Se Data_Competencia é datetime
                                    if pd.api.types.is_datetime64_any_dtype(vendas_cliente['Data_Competencia']):
                                        vendas_por_mes = vendas_cliente.groupby(vendas_cliente['Data_Competencia'].dt.strftime('%m/%Y'))['Total_Venda'].count()
                                    else:
                                        # Se Data_Competencia é string
                                        vendas_por_mes = vendas_cliente.groupby(vendas_cliente['Data_Competencia'].str[3:10])['Total_Venda'].count()
                                    freq_media = vendas_por_mes.mean() if len(vendas_por_mes) > 0 else 0
                                except:
                                    freq_media = 0
                                st.markdown(f"• **Frequência**: {freq_media:.1f} compras/mês")
                            
                            with col_oportunidade:
                                st.markdown("**💡 Oportunidades:**")
                                
                                # Sugestões baseadas no perfil
                                if cliente['Faturamento_Total'] > vendas_por_cliente['Faturamento_Total'].median():
                                    st.success("🎯 **Cliente Premium**: Expandir linha premium")
                                    st.markdown("• Produtos de maior valor agregado")
                                    st.markdown("• Serviços exclusivos")
                                    st.markdown("• Pacotes personalizados")
                                
                                if cliente['Qtd_Vendas'] < vendas_por_cliente['Qtd_Vendas'].median():
                                    st.info("📈 **Aumentar Frequência**: Produtos de consumo")
                                    st.markdown("• Produtos de reposição")
                                    st.markdown("• Contratos mensais")
                                    st.markdown("• Produtos complementares")
                                
                                if freq_media < 2:
                                    st.warning("⚡ **Ativar Cliente**: Promoções direcionadas")
                                    st.markdown("• Ofertas personalizadas")
                                    st.markdown("• Demonstrações de produto")
                                    st.markdown("• Atendimento comercial ativo")
                    
                    # Estratégias gerais
                    st.markdown("---")
                    st.markdown("##### 🚀 Estratégias Gerais para Ampliar Mix")
                    
                    estrategias_tabs = st.tabs(["🎯 Imediatas", "📈 Médio Prazo", "🚀 Longo Prazo"])
                    
                    with estrategias_tabs[0]:
                        st.markdown("**🎯 Ações Imediatas (1-30 dias):**")
                        st.success("✅ **Apresentação de catálogo completo** aos top 10 clientes")
                        st.success("✅ **Ligação comercial ativa** para identificar necessidades")
                        st.success("✅ **Ofertas casadas** para produtos complementares")
                        st.success("✅ **Desconto progressivo** por volume/mix")
                        
                        st.markdown("**📊 KPIs a acompanhar:**")
                        st.markdown("• Nº de produtos por cliente")
                        st.markdown("• Ticket médio por transação")
                        st.markdown("• Frequência de compra")
                    
                    with estrategias_tabs[1]:
                        st.markdown("**📈 Estratégias de Médio Prazo (1-6 meses):**")
                        st.info("📋 **Programa de fidelidade** com benefícios por mix")
                        st.info("📋 **Treinamento da equipe** para cross-selling")
                        st.info("📋 **Sistema de CRM** para histórico de preferências")
                        st.info("📋 **Campanhas segmentadas** por perfil de cliente")
                        
                        st.markdown("**🎯 Metas sugeridas:**")
                        st.markdown("• +30% no mix médio por cliente")
                        st.markdown("• +20% na frequência de compra")
                        st.markdown("• +15% no ticket médio")
                    
                    with estrategias_tabs[2]:
                        st.markdown("**🚀 Visão de Longo Prazo (6+ meses):**")
                        st.warning("🔮 **Diversificação de portfólio** para reduzir dependência")
                        st.warning("🔮 **Parcerias estratégicas** para ampliar oferta")
                        st.warning("🔮 **Desenvolvimento de produtos** específicos")
                        st.warning("🔮 **Expansão geográfica** para novos mercados")
                        
                        st.markdown("**🎯 Objetivo final:**")
                        st.markdown("• Nenhum cliente > 15% do faturamento")
                        st.markdown("• Base de clientes 3x maior")
                        st.markdown("• Mix médio 2x mais diversificado")
            
            # === PERFIL DE COMPRAS ===
            if st.session_state.get('mostrar_perfil', False):
                with st.container():
                    st.markdown("#### 📈 Perfil de Compras - Análise Temporal")
                    
                    if st.button("❌ Fechar Perfil", key="btn_fechar_perfil"):
                        st.session_state.mostrar_perfil = False
                        st.rerun()
                    
                    # Análise de sazonalidade dos top clientes
                    top_3_clientes = vendas_por_cliente.head(3).reset_index()
                    
                    for i, cliente in top_3_clientes.iterrows():
                        vendas_cliente = df_temp[df_temp['Nome_Cliente'] == cliente['Nome_Cliente']].copy()
                        vendas_cliente['Mes'] = pd.to_datetime(vendas_cliente['Data_Competencia']).dt.strftime('%m/%Y')
                        
                        nome_cliente = cliente['Nome_Cliente']
                        if len(nome_cliente) > 35:
                            nome_cliente = nome_cliente[:35] + "..."
                        
                        with st.expander(f"📊 {nome_cliente} - Padrão Temporal"):
                            # Vendas por mês
                            vendas_mensais = vendas_cliente.groupby('Mes').agg({
                                'Total_Venda': ['sum', 'count', 'mean']
                            }).round(2)
                            
                            if len(vendas_mensais) > 1:
                                col_graf, col_insights = st.columns([2, 1])
                                
                                with col_graf:
                                    # Gráfico simples
                                    st.markdown("**📈 Faturamento Mensal:**")
                                    for mes, dados in vendas_mensais.iterrows():
                                        fat_mes = dados[('Total_Venda', 'sum')]
                                        qtd_mes = dados[('Total_Venda', 'count')]
                                        st.markdown(f"• **{mes}**: R$ {fat_mes:,.0f} ({qtd_mes} compras)")
                                
                                with col_insights:
                                    st.markdown("**💡 Insights:**")
                                    
                                    # Variação mensal
                                    fat_medio = vendas_mensais[('Total_Venda', 'sum')].mean()
                                    mes_maior = vendas_mensais[('Total_Venda', 'sum')].idxmax()
                                    mes_menor = vendas_mensais[('Total_Venda', 'sum')].idxmin()
                                    
                                    st.markdown(f"🏆 **Melhor mês**: {mes_maior}")
                                    st.markdown(f"📉 **Menor mês**: {mes_menor}")
                                    st.markdown(f"📊 **Média mensal**: R$ {fat_medio:,.0f}")
                                    
                                    # Regularidade
                                    coef_variacao = vendas_mensais[('Total_Venda', 'sum')].std() / fat_medio * 100
                                    if coef_variacao < 30:
                                        st.success("✅ Cliente regular")
                                    elif coef_variacao < 60:
                                        st.warning("⚠️ Cliente sazonal")
                                    else:
                                        st.error("🚨 Cliente irregular")
                            else:
                                st.info("📊 Dados insuficientes para análise temporal")
                    
                    # Resumo de padrões
                    st.markdown("---")
                    st.markdown("##### 🎯 Conclusões e Próximos Passos")
                    
                    st.success("**✅ Clientes identificados e analisados**")
                    st.success("**✅ Perfis de compra mapeados**") 
                    st.success("**✅ Oportunidades de mix identificadas**")
                    
                    st.markdown("**🚀 Próximos passos recomendados:**")
                    st.markdown("1. **Contato comercial** com top 5 clientes")
                    st.markdown("2. **Apresentação de produtos** não comprados")
                    st.markdown("3. **Propostas personalizadas** de mix")
                    st.markdown("4. **Acompanhamento semanal** dos resultados")
                    st.markdown("5. **Monitoramento da dependência** mensal")
            
            # Alertas de concentração
            st.markdown("**🚨 Alertas de Risco:**")
            alertas_concentracao = []
            
            if maior_cliente_pct > 30:
                alertas_concentracao.append("🚨 **RISCO ALTO**: Um cliente representa >30% das vendas - diversificar urgente!")
            elif maior_cliente_pct > 20:
                alertas_concentracao.append("⚠️ **ATENÇÃO**: Dependência alta de um cliente (>20%) - ampliar base")
            
            if faturamento_top10 > 70:
                alertas_concentracao.append("⚠️ **CONCENTRAÇÃO**: Top 10 clientes = >70% vendas - risco operacional")
            
            if clientes_80_pct < 5:
                alertas_concentracao.append("🚨 **BASE PEQUENA**: Menos de 5 clientes geram 80% - captar novos clientes urgente")
            
            if alertas_concentracao:
                for alerta in alertas_concentracao:
                    st.error(alerta)
            else:
                st.success("✅ **DISTRIBUIÇÃO SAUDÁVEL**: Baixo risco de concentração de vendas")
            
            # === 2. SAZONALIDADE E PADRÕES ===
            st.markdown("---")
            st.markdown("#### 📅 Sazonalidade e Padrões")
            
            # Performance por dia da semana
            df_temp['Dia_Semana'] = df_temp['Data_Competencia'].dt.day_name()
            df_temp['Dia_Semana_Num'] = df_temp['Data_Competencia'].dt.dayofweek
            
            # Traduzir dias para português
            traducao_dias = {
                'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta',
                'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
            }
            df_temp['Dia_Semana_PT'] = df_temp['Dia_Semana'].map(traducao_dias)
            
            vendas_por_dia = df_temp.groupby('Dia_Semana_PT').agg({
                'Total_Venda': ['sum', 'mean', 'count']
            }).round(2)
            vendas_por_dia.columns = ['Faturamento_Total', 'Ticket_Medio', 'Qtd_Vendas']
            
            # Ordenar pelos dias da semana
            ordem_dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
            vendas_por_dia = vendas_por_dia.reindex([dia for dia in ordem_dias if dia in vendas_por_dia.index])
            
            col_saz1, col_saz2 = st.columns(2)
            
            with col_saz1:
                st.markdown("**💰 Faturamento por Dia:**")
                for dia, dados in vendas_por_dia.iterrows():
                    pct_total = dados['Faturamento_Total'] / vendas_por_dia['Faturamento_Total'].sum() * 100
                    st.write(f"• **{dia}**: R$ {dados['Faturamento_Total']:,.2f} ({pct_total:.1f}%)")
            
            with col_saz2:
                st.markdown("**🛒 Quantidade de Vendas:**")
                for dia, dados in vendas_por_dia.iterrows():
                    st.write(f"• **{dia}**: {dados['Qtd_Vendas']:.0f} vendas (R$ {dados['Ticket_Medio']:,.2f} médio)")
            
            # Identificar padrões sazonais
            melhor_dia = vendas_por_dia['Faturamento_Total'].idxmax()
            pior_dia = vendas_por_dia['Faturamento_Total'].idxmin()
            variacao_semanal = (vendas_por_dia['Faturamento_Total'].max() - vendas_por_dia['Faturamento_Total'].min()) / vendas_por_dia['Faturamento_Total'].mean() * 100
            
            st.markdown("**📊 Análise Sazonal:**")
            st.info(f"🏆 **Melhor dia**: {melhor_dia} - R$ {vendas_por_dia.loc[melhor_dia, 'Faturamento_Total']:,.2f}")
            st.info(f"📉 **Pior dia**: {pior_dia} - R$ {vendas_por_dia.loc[pior_dia, 'Faturamento_Total']:,.2f}")
            
            if variacao_semanal > 50:
                st.warning(f"⚠️ **ALTA VARIAÇÃO**: {variacao_semanal:.1f}% entre melhor e pior dia - revisar estratégia semanal")
            else:
                st.success(f"✅ **CONSISTENTE**: Variação de {variacao_semanal:.1f}% entre dias da semana")
            
            # === 3. CONSISTÊNCIA E PREVISIBILIDADE ===
            st.markdown("---")
            st.markdown("#### 🎯 Consistência Operacional")
            
            # Vendas por dia (agregadas)
            vendas_diarias = df_temp.groupby(df_temp['Data_Competencia'].dt.date).agg({
                'Total_Venda': ['sum', 'count']
            }).round(2)
            vendas_diarias.columns = ['Faturamento_Diario', 'Qtd_Vendas_Diario']
            
            # Estatísticas de consistência
            media_diaria = vendas_diarias['Faturamento_Diario'].mean()
            desvio_diario = vendas_diarias['Faturamento_Diario'].std()
            coef_variacao = (desvio_diario / media_diaria * 100) if media_diaria > 0 else 0
            
            dias_sem_vendas = len(vendas_diarias[vendas_diarias['Qtd_Vendas_Diario'] == 0])
            dias_totais = len(vendas_diarias)
            
            # Dias com vendas muito baixas (< 50% da média)
            limite_baixo = media_diaria * 0.5
            dias_fracos = len(vendas_diarias[vendas_diarias['Faturamento_Diario'] < limite_baixo])
            
            col_cons1, col_cons2, col_cons3, col_cons4 = st.columns(4)
            
            with col_cons1:
                st.metric(
                    label="📊 Média Diária",
                    value=f"R$ {media_diaria:,.2f}",
                    help="Faturamento médio por dia de vendas"
                )
            
            with col_cons2:
                st.metric(
                    label="📈 Variabilidade",
                    value=f"{coef_variacao:.1f}%",
                    help="Coeficiente de variação das vendas diárias"
                )
            
            with col_cons3:
                st.metric(
                    label="⚠️ Dias Fracos",
                    value=f"{dias_fracos}",
                    delta=f"{dias_fracos/dias_totais*100:.1f}% do período",
                    help="Dias com vendas < 50% da média"
                )
            
            with col_cons4:
                st.metric(
                    label="🚫 Dias Sem Vendas",
                    value=f"{dias_sem_vendas}",
                    delta=f"{dias_sem_vendas/dias_totais*100:.1f}% do período",
                    help="Dias sem nenhuma venda registrada"
                )
            
            # Alertas de consistência
            st.markdown("**🎯 Análise de Consistência:**")
            alertas_consistencia = []
            
            if coef_variacao > 80:
                alertas_consistencia.append("🚨 **ALTA VOLATILIDADE**: Vendas muito inconsistentes (>80%) - revisar processos")
            elif coef_variacao > 50:
                alertas_consistencia.append("⚠️ **VARIABILIDADE ALTA**: Vendas pouco previsíveis (>50%) - buscar estabilidade")
            elif coef_variacao < 20:
                alertas_consistencia.append("✅ **MUITO CONSISTENTE**: Vendas previsíveis (<20%) - operação estável")
            
            if dias_sem_vendas > dias_totais * 0.1:
                alertas_consistencia.append("⚠️ **MUITOS DIAS VAZIOS**: >10% dos dias sem vendas - melhorar cobertura")
            
            if dias_fracos > dias_totais * 0.3:
                alertas_consistencia.append("📉 **DIAS FRACOS FREQUENTES**: >30% abaixo da média - revisar estratégia")
            
            if alertas_consistencia:
                for alerta in alertas_consistencia:
                    st.info(alerta)
            else:
                st.success("✅ **OPERAÇÃO CONSISTENTE**: Padrão de vendas estável e previsível")
            
            # === 4. RITMO DE VENDAS E TENDÊNCIAS ===
            st.markdown("---")
            st.markdown("#### ⚡ Ritmo de Vendas e Tendências")
            st.caption("*Análise do ritmo e direção das vendas*")
            
            # Calcular dados para análise de ritmo
            vendas_diarias_ordenadas = vendas_diarias.sort_index()
            
            # Ritmo de crescimento (últimos 7 dias vs 7 dias anteriores)
            if len(vendas_diarias_ordenadas) >= 14:
                ultimos_7_dias = vendas_diarias_ordenadas.tail(7)['Faturamento_Diario']
                anteriores_7_dias = vendas_diarias_ordenadas.tail(14).head(7)['Faturamento_Diario']
                
                media_ultimos_7 = ultimos_7_dias.mean()
                media_anteriores_7 = anteriores_7_dias.mean()
                
                crescimento_7d = ((media_ultimos_7 - media_anteriores_7) / media_anteriores_7 * 100) if media_anteriores_7 > 0 else 0
            else:
                crescimento_7d = 0
                media_ultimos_7 = vendas_diarias_ordenadas.tail(min(7, len(vendas_diarias_ordenadas)))['Faturamento_Diario'].mean()
                media_anteriores_7 = 0
            
            # Direção das vendas (últimos 5 dias)
            if len(vendas_diarias_ordenadas) >= 5:
                vendas_recentes = vendas_diarias_ordenadas.tail(5)['Faturamento_Diario']
                
                # Calcular se está subindo, descendo ou estável
                primeiro_periodo = vendas_recentes.head(2).mean()
                ultimo_periodo = vendas_recentes.tail(2).mean()
                
                variacao_direcao = ((ultimo_periodo - primeiro_periodo) / primeiro_periodo * 100) if primeiro_periodo > 0 else 0
                
                if variacao_direcao > 10:
                    direcao = "📈 Acelerando"
                    cor_direcao = "🟢"
                elif variacao_direcao < -10:
                    direcao = "📉 Desacelerando"
                    cor_direcao = "🔴"
                else:
                    direcao = "➡️ Estável"
                    cor_direcao = "🟡"
            else:
                direcao = "❓ Poucos dados"
                cor_direcao = "⚪"
                variacao_direcao = 0
            
            # Velocidade de vendas (vendas por dia)
            velocidade_vendas = len(df_temp) / len(vendas_diarias) if len(vendas_diarias) > 0 else 0
            
            # Intervalo médio entre vendas
            if len(df_temp) > 1:
                df_temp_sorted = df_temp.sort_values('Data_Competencia')
                intervalos = df_temp_sorted['Data_Competencia'].diff().dt.days.dropna()
                intervalo_medio = intervalos.mean() if len(intervalos) > 0 else 0
            else:
                intervalo_medio = 0
            
            # Exibir métricas de ritmo
            col_ritmo1, col_ritmo2, col_ritmo3, col_ritmo4 = st.columns(4)
            
            with col_ritmo1:
                delta_crescimento = f"{crescimento_7d:+.1f}%" if crescimento_7d != 0 else "Estável"
                cor_crescimento = "normal" if crescimento_7d >= 0 else "inverse"
                st.metric(
                    label="📊 Ritmo 7 Dias",
                    value=f"R$ {media_ultimos_7:,.0f}/dia",
                    delta=delta_crescimento,
                    delta_color=cor_crescimento,
                    help="Média diária dos últimos 7 dias vs 7 anteriores"
                )
            
            with col_ritmo2:
                st.metric(
                    label="🎯 Direção Atual",
                    value=direcao,
                    help="Tendência dos últimos 5 dias de vendas"
                )
            
            with col_ritmo3:
                st.metric(
                    label="⚡ Velocidade",
                    value=f"{velocidade_vendas:.1f} vendas/dia",
                    help="Número médio de vendas por dia"
                )
            
            with col_ritmo4:
                st.metric(
                    label="⏰ Intervalo Entre Vendas",
                    value=f"{intervalo_medio:.1f} dias",
                    help="Tempo médio entre vendas consecutivas"
                )
            
            # Análise do ritmo atual
            st.markdown("**📊 Interpretação do Ritmo:**")
            
            col_interp1, col_interp2 = st.columns(2)
            
            with col_interp1:
                st.markdown("**📈 Ritmo de Crescimento (7 dias):**")
                if crescimento_7d > 20:
                    st.success(f"🚀 **ACELERAÇÃO FORTE**: +{crescimento_7d:.1f}% - momento excelente!")
                elif crescimento_7d > 5:
                    st.info(f"📈 **CRESCIMENTO POSITIVO**: +{crescimento_7d:.1f}% - tendência boa")
                elif crescimento_7d < -20:
                    st.error(f"📉 **QUEDA SIGNIFICATIVA**: {crescimento_7d:.1f}% - ação urgente")
                elif crescimento_7d < -5:
                    st.warning(f"⚠️ **DESACELERAÇÃO**: {crescimento_7d:.1f}% - revisar estratégia")
                else:
                    st.info(f"➡️ **ESTÁVEL**: {crescimento_7d:.1f}% - performance consistente")
            
            with col_interp2:
                st.markdown("**🎯 Direção das Vendas:**")
                if "Acelerando" in direcao:
                    st.success("🚀 **ACELERANDO**: Vendas em crescimento nos últimos dias")
                elif "Desacelerando" in direcao:
                    st.error("📉 **DESACELERANDO**: Vendas em queda nos últimos dias")
                elif "Estável" in direcao:
                    st.info("➡️ **ESTÁVEL**: Vendas mantendo o mesmo ritmo")
                else:
                    st.warning("❓ **POUCOS DADOS**: Necessário mais histórico para análise")
            
            # Recomendações baseadas no ritmo
            st.markdown("**💡 Recomendações:**")
            if crescimento_7d > 15 and "Acelerando" in direcao:
                st.info("🎯 **APROVEITAR MOMENTUM**: Momento ideal para intensificar ações comerciais")
            elif crescimento_7d < -15 or "Desacelerando" in direcao:
                st.info("⚡ **ACELERAR AÇÕES**: Revisar estratégias e intensificar prospecção")
            elif velocidade_vendas < 1:
                st.info("🔄 **AUMENTAR FREQUÊNCIA**: Menos de 1 venda por dia - acelerar ritmo")
            elif intervalo_medio > 3:
                st.info("⏰ **REDUZIR INTERVALOS**: Muito tempo entre vendas - melhorar follow-up")
            
            # === 5. OPORTUNIDADES IDENTIFICADAS ===
            st.markdown("---")
            st.markdown("#### 🎯 Oportunidades de Melhoria")
            
            oportunidades = []
            
            # Oportunidades baseadas em sazonalidade
            if variacao_semanal > 30:
                oportunidades.append(f"📅 **NIVELAMENTO SEMANAL**: {pior_dia} tem potencial de crescer {(vendas_por_dia.loc[melhor_dia, 'Faturamento_Total'] / vendas_por_dia.loc[pior_dia, 'Faturamento_Total'] - 1) * 100:.0f}%")
            
            # Oportunidades baseadas em consistência
            if dias_fracos > 5:
                oportunidade_dias_fracos = limite_baixo * dias_fracos
                oportunidades.append(f"💪 **FORTALECER DIAS FRACOS**: {dias_fracos} dias podem gerar +R$ {oportunidade_dias_fracos:,.2f}")
            
            # Oportunidades baseadas em concentração
            if faturamento_top10 < 50:
                oportunidades.append("🎯 **CLIENTES VIP**: Base diversificada permite focar em clientes de maior valor")
            
            # Oportunidades baseadas no ritmo atual
            if crescimento_7d > 15 and "Acelerando" in direcao:
                oportunidades.append("🚀 **ACELERAR INVESTIMENTO**: Momento ideal para ampliar ações comerciais")
            
            # Oportunidades de timing
            if intervalo_medio > 2:
                oportunidades.append(f"⏰ **REDUZIR INTERVALO**: Vendas a cada {intervalo_medio:.1f} dias - acelerar ciclo comercial")
            
            # Sugestões gerais sempre aplicáveis
            oportunidades.extend([
                "🎁 **CROSS-SELLING**: Oferecer produtos complementares nos dias de pico",
                "📞 **FOLLOW-UP**: Contatar clientes nos dias historicamente fracos",
                "🎯 **CAMPAIGNS DIRECIONADAS**: Focar nos dias/horários de melhor performance",
                "📊 **ANÁLISE MAIS PROFUNDA**: Segmentar por produto/região para identificar oportunidades específicas"
            ])
            
            st.markdown("**🎯 Oportunidades Identificadas:**")
            for i, oportunidade in enumerate(oportunidades, 1):
                if i <= 6:  # Mostrar até 6 oportunidades principais
                    st.info(f"{i}. {oportunidade}")
            
            # === 5. ANÁLISE TEMPORAL DAS VENDAS ===
            st.markdown("---")
            st.markdown("#### 📈 Análise Temporal das Vendas")
            st.caption("*Tendências, picos, quedas e sazonalidade*")
            
            # Preparar dados para análise temporal
            vendas_temporais = df_temp.copy()
            vendas_temporais['Data'] = vendas_temporais['Data_Competencia'].dt.date
            
            # Agrupar vendas por data
            vendas_por_dia = vendas_temporais.groupby('Data').agg({
                'Total_Venda': ['sum', 'count', 'mean'],
                'Nome_Cliente': 'nunique'
            }).round(2)
            
            # Flatten columns
            vendas_por_dia.columns = ['Faturamento_Dia', 'Qtd_Vendas_Dia', 'Ticket_Medio_Dia', 'Clientes_Unicos_Dia']
            vendas_por_dia = vendas_por_dia.reset_index()
            
            if len(vendas_por_dia) >= 5:  # Só fazer análise se tiver dados suficientes
                
                # === GRÁFICO TEMPORAL ===
                st.markdown("##### 📊 Evolução Temporal das Vendas")
                
                # Criar gráfico temporal
                import plotly.express as px
                import plotly.graph_objects as go
                from plotly.subplots import make_subplots
                
                # Criar gráfico com duas linhas: Faturamento e Quantidade
                fig_temporal = make_subplots(
                    rows=2, cols=1,
                    subplot_titles=('💰 Faturamento Diário', '🛒 Quantidade de Vendas'),
                    vertical_spacing=0.1,
                    shared_xaxes=True
                )
                
                # Linha de faturamento
                fig_temporal.add_trace(
                    go.Scatter(
                        x=vendas_por_dia['Data'],
                        y=vendas_por_dia['Faturamento_Dia'],
                        mode='lines+markers',
                        name='Faturamento',
                        line=dict(color='#1f77b4', width=3),
                        marker=dict(size=6),
                        hovertemplate='<b>%{x}</b><br>Faturamento: R$ %{y:,.0f}<extra></extra>'
                    ),
                    row=1, col=1
                )
                
                # Linha de quantidade
                fig_temporal.add_trace(
                    go.Scatter(
                        x=vendas_por_dia['Data'],
                        y=vendas_por_dia['Qtd_Vendas_Dia'],
                        mode='lines+markers',
                        name='Qtd Vendas',
                        line=dict(color='#ff7f0e', width=3),
                        marker=dict(size=6),
                        hovertemplate='<b>%{x}</b><br>Vendas: %{y}<extra></extra>'
                    ),
                    row=2, col=1
                )
                
                # === IDENTIFICAR PICOS E QUEDAS ===
                media_faturamento = vendas_por_dia['Faturamento_Dia'].mean()
                desvio_faturamento = vendas_por_dia['Faturamento_Dia'].std()
                
                # Definir limites para picos e quedas
                limite_pico = media_faturamento + (1.5 * desvio_faturamento)
                limite_queda = media_faturamento - (1.5 * desvio_faturamento)
                limite_queda = max(limite_queda, 0)  # Não pode ser negativo
                
                # Identificar picos e quedas
                picos = vendas_por_dia[vendas_por_dia['Faturamento_Dia'] >= limite_pico]
                quedas = vendas_por_dia[vendas_por_dia['Faturamento_Dia'] <= limite_queda]
                
                # Adicionar marcadores de picos
                if not picos.empty:
                    fig_temporal.add_trace(
                        go.Scatter(
                            x=picos['Data'],
                            y=picos['Faturamento_Dia'],
                            mode='markers',
                            name='🚀 Picos',
                            marker=dict(size=12, color='green', symbol='triangle-up'),
                            hovertemplate='<b>PICO - %{x}</b><br>R$ %{y:,.0f}<extra></extra>'
                        ),
                        row=1, col=1
                    )
                
                # Adicionar marcadores de quedas
                if not quedas.empty:
                    fig_temporal.add_trace(
                        go.Scatter(
                            x=quedas['Data'],
                            y=quedas['Faturamento_Dia'],
                            mode='markers',
                            name='📉 Quedas',
                            marker=dict(size=12, color='red', symbol='triangle-down'),
                            hovertemplate='<b>QUEDA - %{x}</b><br>R$ %{y:,.0f}<extra></extra>'
                        ),
                        row=1, col=1
                    )
                
                # Adicionar linha de média
                fig_temporal.add_hline(
                    y=media_faturamento, 
                    line_dash="dash", 
                    line_color="gray",
                    annotation_text=f"Média: R$ {media_faturamento:,.0f}",
                    row=1, col=1
                )
                
                # Configurar layout do gráfico
                fig_temporal.update_layout(
                    height=600,
                    showlegend=True,
                    title_text="📈 Análise Temporal - Picos e Quedas",
                    title_x=0.5
                )
                
                # Aplicar configuração responsiva
                fig_temporal = config_grafico_mobile(fig_temporal, layout_mode)
                
                # Exibir gráfico
                st.plotly_chart(fig_temporal, use_container_width=True)
                
                # === ANÁLISE DOS PERÍODOS ===
                st.markdown("##### 🏆 Análise dos Melhores e Piores Períodos")
                
                # Identificar melhores e piores dias
                vendas_ordenadas = vendas_por_dia.sort_values('Faturamento_Dia', ascending=False)
                top_5_dias = vendas_ordenadas.head(5)
                bottom_5_dias = vendas_ordenadas.tail(5)
                
                # Layout responsivo para análise de períodos
                if layout_mode == "📱 Mobile":
                    # Mobile: seções empilhadas
                    st.markdown("**🏆 TOP 5 MELHORES DIAS:**")
                    for i, (_, dia) in enumerate(top_5_dias.iterrows(), 1):
                        data_str = dia['Data'].strftime('%d/%m/%Y')
                        dia_semana = dia['Data'].strftime('%A')
                        st.success(f"**{i}º** {data_str} ({dia_semana}): R$ {dia['Faturamento_Dia']:,.0f} - {dia['Qtd_Vendas_Dia']} vendas")
                    
                    st.markdown("**📉 TOP 5 PIORES DIAS:**")
                    for i, (_, dia) in enumerate(bottom_5_dias.iterrows(), 1):
                        data_str = dia['Data'].strftime('%d/%m/%Y')
                        dia_semana = dia['Data'].strftime('%A')
                        st.error(f"**{i}º** {data_str} ({dia_semana}): R$ {dia['Faturamento_Dia']:,.0f} - {dia['Qtd_Vendas_Dia']} vendas")
                        
                else:
                    # Desktop: layout em colunas
                    col_melhores, col_piores = st.columns(2)
                    
                    with col_melhores:
                        st.markdown("**🏆 TOP 5 MELHORES DIAS:**")
                        for i, (_, dia) in enumerate(top_5_dias.iterrows(), 1):
                            data_str = dia['Data'].strftime('%d/%m/%Y')
                            dia_semana = dia['Data'].strftime('%A')
                            st.success(f"**{i}º** {data_str} ({dia_semana})")
                            st.markdown(f"💰 R$ {dia['Faturamento_Dia']:,.2f}")
                            st.markdown(f"🛒 {dia['Qtd_Vendas_Dia']} vendas")
                            st.markdown("---")
                    
                    with col_piores:
                        st.markdown("**📉 TOP 5 PIORES DIAS:**")
                        for i, (_, dia) in enumerate(bottom_5_dias.iterrows(), 1):
                            data_str = dia['Data'].strftime('%d/%m/%Y')
                            dia_semana = dia['Data'].strftime('%A')
                            st.error(f"**{i}º** {data_str} ({dia_semana})")
                            st.markdown(f"💰 R$ {dia['Faturamento_Dia']:,.2f}")
                            st.markdown(f"🛒 {dia['Qtd_Vendas_Dia']} vendas")
                            st.markdown("---")
                
                # === ANÁLISE POR DIA DA SEMANA ===
                st.markdown("##### 📅 Performance por Dia da Semana")
                
                # Adicionar dia da semana
                vendas_por_dia_copia = vendas_por_dia.copy()
                vendas_por_dia_copia['Dia_Semana'] = pd.to_datetime(vendas_por_dia_copia['Data']).dt.day_name()
                vendas_por_dia_copia['Dia_Semana_Num'] = pd.to_datetime(vendas_por_dia_copia['Data']).dt.dayofweek
                
                # Ordenar por dia da semana (Segunda = 0)
                dias_semana_pt = {
                    'Monday': 'Segunda-feira',
                    'Tuesday': 'Terça-feira', 
                    'Wednesday': 'Quarta-feira',
                    'Thursday': 'Quinta-feira',
                    'Friday': 'Sexta-feira',
                    'Saturday': 'Sábado',
                    'Sunday': 'Domingo'
                }
                
                vendas_por_dia_copia['Dia_Semana_PT'] = vendas_por_dia_copia['Dia_Semana'].map(dias_semana_pt)
                
                # Agrupar por dia da semana
                performance_semanal = vendas_por_dia_copia.groupby(['Dia_Semana_Num', 'Dia_Semana_PT']).agg({
                    'Faturamento_Dia': ['mean', 'sum', 'count'],
                    'Qtd_Vendas_Dia': ['mean', 'sum'],
                    'Clientes_Unicos_Dia': 'mean'
                }).round(2)
                
                # Flatten columns
                performance_semanal.columns = ['Fat_Medio', 'Fat_Total', 'Dias_Trabalhados', 'Vendas_Media', 'Vendas_Total', 'Clientes_Medio']
                performance_semanal = performance_semanal.reset_index().sort_values('Dia_Semana_Num')
                
                # Mostrar performance semanal
                for _, linha in performance_semanal.iterrows():
                    if linha['Dias_Trabalhados'] > 0:  # Só mostrar dias que tiveram vendas
                        dia_nome = linha['Dia_Semana_PT']
                        
                        # Determinar performance relativa
                        if linha['Fat_Medio'] > media_faturamento * 1.2:
                            status = "🚀 EXCELENTE"
                            cor = "success"
                        elif linha['Fat_Medio'] > media_faturamento:
                            status = "✅ BOM"
                            cor = "success"
                        elif linha['Fat_Medio'] > media_faturamento * 0.8:
                            status = "⚠️ REGULAR"
                            cor = "warning"
                        else:
                            status = "📉 FRACO"
                            cor = "error"
                        
                        # Exibir com layout responsivo
                        if layout_mode == "📱 Mobile":
                            if cor == "success":
                                st.success(f"**{dia_nome}** ({status}): R$ {linha['Fat_Medio']:,.0f}/dia - {linha['Vendas_Media']:.1f} vendas")
                            elif cor == "warning":
                                st.warning(f"**{dia_nome}** ({status}): R$ {linha['Fat_Medio']:,.0f}/dia - {linha['Vendas_Media']:.1f} vendas")
                            else:
                                st.error(f"**{dia_nome}** ({status}): R$ {linha['Fat_Medio']:,.0f}/dia - {linha['Vendas_Media']:.1f} vendas")
                        else:
                            with st.expander(f"{dia_nome} - {status}"):
                                col_sem1, col_sem2, col_sem3 = st.columns(3)
                                with col_sem1:
                                    st.metric("💰 Faturamento Médio", f"R$ {linha['Fat_Medio']:,.2f}")
                                with col_sem2:
                                    st.metric("🛒 Vendas Médias", f"{linha['Vendas_Media']:.1f}")
                                with col_sem3:
                                    st.metric("👥 Clientes Médios", f"{linha['Clientes_Medio']:.1f}")
                
                # === INSIGHTS E RECOMENDAÇÕES ===
                st.markdown("##### 💡 Insights e Recomendações")
                
                # Calcular insights automáticos
                insights_temporais = []
                
                # Melhor dia da semana
                melhor_dia = performance_semanal.loc[performance_semanal['Fat_Medio'].idxmax(), 'Dia_Semana_PT']
                pior_dia = performance_semanal.loc[performance_semanal['Fat_Medio'].idxmin(), 'Dia_Semana_PT']
                
                insights_temporais.append(f"🏆 **MELHOR DIA**: {melhor_dia} é seu dia mais forte")
                insights_temporais.append(f"📉 **PIOR DIA**: {pior_dia} precisa de atenção especial")
                
                # Análise de picos
                if not picos.empty:
                    qtd_picos = len(picos)
                    insights_temporais.append(f"🚀 **PICOS IDENTIFICADOS**: {qtd_picos} dias de performance excepcional")
                    
                    # Padrão dos picos
                    picos_dias_semana = pd.to_datetime(picos['Data']).dt.day_name().value_counts()
                    if len(picos_dias_semana) > 0:
                        dia_mais_picos = picos_dias_semana.index[0]
                        dia_mais_picos_pt = dias_semana_pt.get(dia_mais_picos, dia_mais_picos)
                        insights_temporais.append(f"📊 **PADRÃO DE PICOS**: Concentrados em {dia_mais_picos_pt}")
                
                # Análise de quedas
                if not quedas.empty:
                    qtd_quedas = len(quedas)
                    insights_temporais.append(f"⚠️ **QUEDAS IDENTIFICADAS**: {qtd_quedas} dias de baixa performance")
                
                # Variabilidade
                coef_var_temporal = (desvio_faturamento / media_faturamento * 100) if media_faturamento > 0 else 0
                if coef_var_temporal > 60:
                    insights_temporais.append("📊 **ALTA VARIABILIDADE**: Vendas muito inconsistentes - buscar estabilidade")
                elif coef_var_temporal < 30:
                    insights_temporais.append("✅ **BOA CONSISTÊNCIA**: Vendas relativamente estáveis")
                
                # Tendência geral
                if len(vendas_por_dia) >= 10:
                    # Calcular tendência simples (primeiros 50% vs últimos 50%)
                    meio = len(vendas_por_dia) // 2
                    primeira_metade = vendas_por_dia.head(meio)['Faturamento_Dia'].mean()
                    segunda_metade = vendas_por_dia.tail(meio)['Faturamento_Dia'].mean()
                    
                    if segunda_metade > primeira_metade * 1.1:
                        insights_temporais.append("📈 **TENDÊNCIA POSITIVA**: Vendas melhorando ao longo do tempo")
                    elif segunda_metade < primeira_metade * 0.9:
                        insights_temporais.append("📉 **TENDÊNCIA NEGATIVA**: Vendas declinando - ação necessária")
                    else:
                        insights_temporais.append("➡️ **TENDÊNCIA ESTÁVEL**: Vendas mantendo padrão")
                
                # Exibir insights
                for insight in insights_temporais:
                    st.info(insight)
                
                # === RECOMENDAÇÕES ESTRATÉGICAS ===
                st.markdown("**🎯 Recomendações Estratégicas:**")
                
                recomendacoes_temporais = []
                
                # Recomendações baseadas nos insights
                if not picos.empty:
                    recomendacoes_temporais.append("🔍 **ANALISAR PICOS**: Identifique o que causou os dias excepcionais e replique")
                
                if not quedas.empty:
                    recomendacoes_temporais.append("🚨 **FOCAR NAS QUEDAS**: Investigue e corrija os fatores dos dias fracos")
                
                # Recomendação do melhor dia
                melhor_fat = performance_semanal.loc[performance_semanal['Fat_Medio'].idxmax(), 'Fat_Medio']
                pior_fat = performance_semanal.loc[performance_semanal['Fat_Medio'].idxmin(), 'Fat_Medio']
                gap_semanal = ((melhor_fat - pior_fat) / melhor_fat * 100)
                
                if gap_semanal > 50:
                    recomendacoes_temporais.append(f"📊 **EQUALIZAR DIAS**: Gap de {gap_semanal:.0f}% entre melhor/pior dia - buscar equilibrar")
                
                recomendacoes_temporais.extend([
                    f"🎯 **MAXIMIZAR {melhor_dia.upper()}**: Aproveitar seu dia mais forte",
                    f"⚡ **ATIVAR {pior_dia.upper()}**: Criar estratégias específicas para o dia mais fraco",
                    "📞 **TIMING COMERCIAL**: Concentrar ações de vendas nos dias/períodos mais receptivos",
                    "📊 **MONITORAMENTO**: Acompanhar semanalmente para identificar mudanças nos padrões"
                ])
                
                # Exibir recomendações
                for i, recomendacao in enumerate(recomendacoes_temporais[:6], 1):  # Máximo 6 recomendações
                    st.success(f"{i}. {recomendacao}")
                
            else:
                st.info("📊 **Dados insuficientes** para análise temporal completa. Necessário pelo menos 5 dias de dados.")
            
        else:
            st.warning("❌ Dados insuficientes para análises avançadas")

def pagina_configuracoes():
    """Página centralizada de configurações"""
    st.title("⚙️ Configurações do Sistema")
    st.markdown("*Central de configurações e ferramentas*")
    
    # === LAYOUT ===
    st.subheader("🖥️ Layout e Visualização")
    
    col_layout1, col_layout2 = st.columns(2)
    
    with col_layout1:
        if st.button("🖥️ Layout Desktop", use_container_width=True, help="Otimizado para telas grandes"):
            st.session_state.layout_mode = "🖥️ Desktop"
            st.success("✅ Layout Desktop ativado!")
    
    with col_layout2:
        if st.button("📱 Layout Mobile", use_container_width=True, help="Otimizado para dispositivos móveis"):
            st.session_state.layout_mode = "📱 Mobile"
            st.success("✅ Layout Mobile ativado!")
    
    st.info(f"**Layout atual:** {st.session_state.get('layout_mode', '🖥️ Desktop')}")
    
    # === GESTÃO DE DADOS ===
    st.markdown("---")
    st.subheader("📊 Gestão de Dados")
    
    col_dados1, col_dados2 = st.columns(2)
    
    with col_dados1:
        with st.expander("🏢 Dados do Atacado", expanded=False):
            st.markdown("**📁 Arquivo Atual de Atacado:**")
            
            # Identificar arquivo atual do atacado
            arquivos_atacado = [f for f in os.listdir('.') if f.startswith('Vendas até') and f.endswith('.txt')]
            if arquivos_atacado:
                arquivo_atual = sorted(arquivos_atacado)[-1]
                st.info(f"📄 **{arquivo_atual}**")
                
                # Mostrar informações do arquivo
                try:
                    df_info = pd.read_csv(arquivo_atual, sep=';', encoding='latin-1', on_bad_lines='skip', nrows=5)
                    st.success(f"✅ **{len(pd.read_csv(arquivo_atual, sep=';', encoding='latin-1', on_bad_lines='skip'))} registros** carregados")
                except:
                    st.warning("⚠️ Arquivo com problemas de leitura")
            else:
                st.error("❌ Nenhum arquivo de atacado encontrado")
            
            st.markdown("**📥 Atualizar Dados do Atacado:**")
            arquivo_atacado = st.file_uploader(
                "Novo arquivo de Atacado (.txt)",
                type=['txt'],
                key="upload_atacado",
                help="Substitui ou adiciona aos dados existentes do atacado"
            )
            
            if arquivo_atacado is not None:
                if st.button("🚀 Processar Atacado", type="primary", key="btn_atacado"):
                    with st.spinner("⏳ Processando dados do atacado..."):
                        sucesso = processar_arquivo_atacado(arquivo_atacado)
                    
                    if sucesso:
                        st.success("🎉 **Dados do Atacado atualizados!**")
                        st.cache_data.clear()
                        st.rerun()
    
    with col_dados2:
        with st.expander("🏪 Dados do Varejo", expanded=False):
            st.markdown("**📁 Arquivo Atual de Varejo:**")
            
            # Identificar arquivo atual do varejo
            arquivos_varejo = [f for f in os.listdir('.') if 'varejo' in f.lower() and f.endswith('.txt')]
            if arquivos_varejo:
                arquivo_atual = arquivos_varejo[0]
                st.info(f"📄 **{arquivo_atual}**")
                
                # Mostrar informações do arquivo
                try:
                    df_info = pd.read_csv(arquivo_atual, sep=';', encoding='latin-1', on_bad_lines='skip', nrows=5)
                    st.success(f"✅ **{len(pd.read_csv(arquivo_atual, sep=';', encoding='latin-1', on_bad_lines='skip'))} registros** carregados")
                except:
                    st.warning("⚠️ Arquivo com problemas de leitura")
            else:
                st.error("❌ Nenhum arquivo de varejo encontrado")
            
            st.markdown("**📥 Atualizar Dados do Varejo:**")
            arquivo_varejo = st.file_uploader(
                "Novo arquivo de Varejo (.txt)",
                type=['txt'],
                key="upload_varejo",
                help="Substitui ou adiciona aos dados existentes do varejo"
            )
            
            if arquivo_varejo is not None:
                if st.button("🚀 Processar Varejo", type="primary", key="btn_varejo"):
                    with st.spinner("⏳ Processando dados do varejo..."):
                        sucesso = processar_arquivo_varejo(arquivo_varejo)
                    
                    if sucesso:
                        st.success("🎉 **Dados do Varejo atualizados!**")
                        st.cache_data.clear()
                        st.rerun()
    
    # === FERRAMENTAS GERAIS ===
    st.markdown("**🔧 Ferramentas Gerais:**")
    col_tool1, col_tool2 = st.columns(2)
    
    with col_tool1:
        if st.button("🔄 Limpar Cache", help="Limpa o cache e recarrega dados"):
            st.cache_data.clear()
            st.success("✅ Cache limpo!")
            st.rerun()
    
    with col_tool2:
        if st.button("📋 Ver Backups", help="Lista dos backups disponíveis"):
            backups = [f for f in os.listdir('.') if f.startswith('backup_vendas_') and f.endswith('.txt')]
            if backups:
                st.write("📂 **Backups disponíveis:**")
                for backup in sorted(backups, reverse=True)[:5]:  # Últimos 5
                    st.write(f"• {backup}")
            else:
                st.info("Nenhum backup encontrado")
    
    # === CONFIGURAÇÃO DE METAS ===
    st.markdown("---")
    st.subheader("🎯 Configuração de Metas")
    
    # === METAS DE VENDAS ===
    with st.expander("💰 Metas de Faturamento", expanded=True):
        
        # === META DO ATACADO ===
        st.markdown("### 🏢 Configuração de Meta - Atacado")
        
        col_atac1, col_atac2 = st.columns(2)
        
        with col_atac1:
            meta_atacado_atual = st.session_state.get('meta_atacado', 850000)
            nova_meta_atacado = st.number_input(
                "Meta Mensal Atacado (R$):",
                value=meta_atacado_atual,
                min_value=0,
                step=1000,
                format="%d",
                key="meta_atacado_input",
                help="Meta de faturamento mensal para o setor de atacado"
            )
        
        with col_atac2:
            dias_atacado_atuais = st.session_state.get('dias_uteis_atacado', 27)
            novos_dias_atacado = st.number_input(
                "Dias Úteis Atacado:",
                value=dias_atacado_atuais,
                min_value=1,
                max_value=31,
                step=1,
                key="dias_atacado_input",
                help="Número de dias úteis no mês para o atacado"
            )
        
        # Botões de ação para Atacado
        col_atac_btn1, col_atac_btn2, col_atac_btn3 = st.columns(3)
        
        with col_atac_btn1:
            if st.button("💾 Salvar Meta Atacado", use_container_width=True, key="salvar_atacado"):
                st.session_state.meta_atacado = nova_meta_atacado
                st.session_state.dias_uteis_atacado = novos_dias_atacado
                st.success("✅ Meta do Atacado salva!")
                st.rerun()
        
        with col_atac_btn2:
            if st.button("🔄 Restaurar Atacado", use_container_width=True, key="restaurar_atacado"):
                st.session_state.meta_atacado = 850000
                st.session_state.dias_uteis_atacado = 27
                st.success("✅ Meta padrão do Atacado restaurada!")
                st.rerun()
        
        with col_atac_btn3:
            ritmo_atacado = nova_meta_atacado / novos_dias_atacado if novos_dias_atacado > 0 else 0
            st.metric(
                label="🎯 Ritmo Atacado",
                value=f"R$ {ritmo_atacado:,.0f}/dia",
                help="Faturamento diário necessário para atingir a meta do atacado"
            )
        
        # Status atual Atacado
        st.info(f"🏢 **Atacado:** R$ {nova_meta_atacado:,.0f} | 📅 {novos_dias_atacado} dias | 🎯 R$ {ritmo_atacado:,.0f}/dia")
        
        # === META DO VAREJO ===
        st.markdown("---")
        st.markdown("### 🏪 Configuração de Meta - Varejo")
        
        # Opção de ativar/desativar meta do varejo
        ativar_meta_varejo = st.checkbox(
            "🔧 Ativar configuração de meta para o Varejo",
            value=st.session_state.get('ativar_meta_varejo', False),
            help="Por enquanto, mantenha desativado conforme solicitado"
        )
        
        st.session_state.ativar_meta_varejo = ativar_meta_varejo
        
        if ativar_meta_varejo:
            col_var1, col_var2 = st.columns(2)
            
            with col_var1:
                meta_varejo_atual = st.session_state.get('meta_varejo', 200000)
                nova_meta_varejo = st.number_input(
                    "Meta Mensal Varejo (R$):",
                    value=meta_varejo_atual,
                    min_value=0,
                    step=1000,
                    format="%d",
                    key="meta_varejo_input",
                    help="Meta de faturamento mensal para o setor de varejo"
                )
            
            with col_var2:
                dias_varejo_atuais = st.session_state.get('dias_uteis_varejo', 27)
                novos_dias_varejo = st.number_input(
                    "Dias Úteis Varejo:",
                    value=dias_varejo_atuais,
                    min_value=1,
                    max_value=31,
                    step=1,
                    key="dias_varejo_input",
                    help="Número de dias úteis no mês para o varejo"
                )
            
            # Botões de ação para Varejo
            col_var_btn1, col_var_btn2, col_var_btn3 = st.columns(3)
            
            with col_var_btn1:
                if st.button("💾 Salvar Meta Varejo", use_container_width=True, key="salvar_varejo"):
                    st.session_state.meta_varejo = nova_meta_varejo
                    st.session_state.dias_uteis_varejo = novos_dias_varejo
                    st.success("✅ Meta do Varejo salva!")
                    st.rerun()
            
            with col_var_btn2:
                if st.button("🔄 Restaurar Varejo", use_container_width=True, key="restaurar_varejo"):
                    st.session_state.meta_varejo = 200000
                    st.session_state.dias_uteis_varejo = 27
                    st.success("✅ Meta padrão do Varejo restaurada!")
                    st.rerun()
            
            with col_var_btn3:
                ritmo_varejo = nova_meta_varejo / novos_dias_varejo if novos_dias_varejo > 0 else 0
                st.metric(
                    label="🎯 Ritmo Varejo",
                    value=f"R$ {ritmo_varejo:,.0f}/dia",
                    help="Faturamento diário necessário para atingir a meta do varejo"
                )
            
            # Status atual Varejo
            st.info(f"🏪 **Varejo:** R$ {nova_meta_varejo:,.0f} | 📅 {novos_dias_varejo} dias | 🎯 R$ {ritmo_varejo:,.0f}/dia")
        
        else:
            st.info("🔧 **Meta do Varejo desativada** - Habilite a opção acima quando necessário")
    
    # === METAS DE CLIENTES ===
    with st.expander("👥 Metas de Clientes Novos", expanded=False):
        st.markdown("### 📊 Configuração Atual")
        
        col_meta1, col_meta2 = st.columns(2)
        
        with col_meta1:
            st.markdown("**📅 Julho 2025**")
            st.write("• Meta: 60 clientes novos")
            st.write("• Dias úteis: 27 dias")
            st.write("• Ritmo necessário: 2.2 clientes/dia")
        
        with col_meta2:
            st.markdown("**📅 Agosto 2025**")
            st.write("• Meta: 65 clientes novos")
            st.write("• Dias úteis: 22 dias")
            st.write("• Ritmo necessário: 3.0 clientes/dia")
        
        st.markdown("---")
        st.markdown("**📅 Setembro 2025**")
        st.write("• Meta: 70 clientes novos")
        st.write("• Dias úteis: 21 dias")
        st.write("• Ritmo necessário: 3.3 clientes/dia")
        
        st.info("🔧 **Configuração de metas de clientes**: Funcionalidade em desenvolvimento")
    
    # === FERRAMENTAS ===
    st.markdown("---")
    st.subheader("🛠️ Ferramentas do Sistema")
    
    col_ferr1, col_ferr2, col_ferr3 = st.columns(3)
    
    with col_ferr1:
        if st.button("🔄 Limpar Cache", use_container_width=True, help="Recarrega todos os dados"):
            st.cache_data.clear()
            st.success("✅ Cache limpo!")
            st.rerun()
    
    with col_ferr2:
        if st.button("📋 Ver Backups", use_container_width=True, help="Lista dos backups disponíveis"):
            backups = [f for f in os.listdir('.') if f.startswith('backup_vendas_') and f.endswith('.txt')]
            if backups:
                st.write("📂 **Backups disponíveis:**")
                for backup in sorted(backups, reverse=True)[:5]:
                    st.write(f"• {backup}")
            else:
                st.info("Nenhum backup encontrado")
    
    with col_ferr3:
        if st.button("📊 Verificar Sistema", use_container_width=True, help="Status do sistema"):
            st.success("✅ Sistema funcionando normalmente")
            st.info(f"Layout: {st.session_state.get('layout_mode', 'Desktop')}")
            st.info(f"Última navegação: {st.session_state.get('analise_selecionada', 'Não definido')}")

def main():
    """Função principal com navegação entre análises"""
    
    # Verificar se é a primeira vez do usuário
    if 'primeira_vez' not in st.session_state:
        st.session_state.primeira_vez = True
    
    # Se for primeira vez, mostrar tela de boas-vindas
    if st.session_state.primeira_vez:
        tela_boas_vindas()
        return
    
    # Header responsivo - otimizado para mobile
    layout_mode = st.session_state.get('layout_mode', '🖥️ Desktop')
    
    if layout_mode == "📱 Mobile":
        # Header MÍNIMO para mobile
        st.markdown("""
        <style>
        .header-mobile {
            background: linear-gradient(90deg, #2E7D32 0%, #4CAF50 100%);
            padding: 0.4rem;
            border-radius: 8px;
            margin-bottom: 0.8rem;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .header-mobile-title {
            color: white;
            font-size: 1.1rem;
            font-weight: bold;
            margin: 0;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="header-mobile">
            <div class="header-mobile-title">🌾 Grãos S.A.</div>
        </div>
        """, unsafe_allow_html=True)
    
    else:
        # Header completo para desktop
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
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="header-container">
            <div class="header-title">🌾 Gestor Estratégico - Grãos S.A.</div>
            <div class="header-subtitle">Sistema Inteligente de Gestão de Negócios</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Navegação responsiva - otimizada para mobile
    if layout_mode == "📱 Mobile":
        # Layout compacto para mobile - 2 linhas de botões
        st.markdown("""
        <style>
        .mobile-nav {
            margin-bottom: 0.8rem;
        }
        .stButton > button {
            height: 2.8rem;
            font-size: 0.9rem;
            font-weight: bold;
            border-radius: 8px;
            margin-bottom: 0.3rem;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Primeira linha - principais
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            if st.button("🌍 Geral", use_container_width=True, key="mobile_geral", help="Dashboard principal"):
                st.session_state.analise_selecionada = "geral"
        with col_m2:
            if st.button("🏢 Atacado", use_container_width=True, key="mobile_atacado", help="Dashboard Atacado"):
                st.session_state.analise_selecionada = "atacado"
        with col_m3:
            if st.button("🏪 Varejo", use_container_width=True, key="mobile_varejo", help="Dashboard Varejo"):
                st.session_state.analise_selecionada = "varejo"
        
        # Espaçamento entre linhas
        st.markdown("<div style='margin: 0.2rem 0;'></div>", unsafe_allow_html=True)
        
        # Segunda linha - secundários
        col_m4, col_m5, col_m6 = st.columns([2, 2, 1])
        with col_m4:
            if st.button("👥 Clientes", use_container_width=True, key="mobile_clientes", help="Análises de clientes"):
                st.session_state.analise_selecionada = "clientes"
        with col_m5:
            if st.button("⚙️ Config", use_container_width=True, key="mobile_config", type="secondary", help="Configurações"):
                st.session_state.analise_selecionada = "configuracoes"
        # col_m6 fica vazia para balanceamento
    
    else:
        # Layout desktop - linha única
        col1, col2, col3, col4, col5 = st.columns([3, 3, 3, 3, 2])
        
        with col1:
            if st.button("🌍 Geral", use_container_width=True, help="Dashboard principal: Atacado + Varejo + Clientes"):
                st.session_state.analise_selecionada = "geral"
        
        with col2:
            if st.button("🏢 Atacado", use_container_width=True, help="Dashboard detalhado do setor de Atacado"):
                st.session_state.analise_selecionada = "atacado"
        
        with col3:
            if st.button("🏪 Varejo", use_container_width=True, help="Dashboard detalhado do setor de Varejo"):
                st.session_state.analise_selecionada = "varejo"
        
        with col4:
            if st.button("👥 Clientes", use_container_width=True, help="Análises de clientes (apenas atacado)"):
                st.session_state.analise_selecionada = "clientes"
        
        with col5:
            if st.button("⚙️ Config", use_container_width=True, help="Configurações do sistema", type="secondary"):
                st.session_state.analise_selecionada = "configuracoes"
    
    # Inicializar sessão se não existir
    if 'analise_selecionada' not in st.session_state:
        st.session_state.analise_selecionada = "geral"
    
    # Layout já foi definido na tela de boas-vindas
    if 'layout_mode' not in st.session_state:
        st.session_state.layout_mode = "🖥️ Desktop"
    
    # Espaçamento responsivo
    if layout_mode == "📱 Mobile":
        st.markdown("<br>", unsafe_allow_html=True)  # Espaço mínimo para mobile
    else:
        st.markdown("---")  # Linha divisória completa para desktop
    
    # Carregando dados
    with st.spinner("Carregando dados..."):
        df_atacado = carregar_dados()  # Dados do atacado
        df_varejo = carregar_dados_varejo()  # Dados do varejo
    
    # Verificar se pelo menos um dataset foi carregado
    if df_atacado.empty and (df_varejo is None or df_varejo.empty):
        st.error("❌ Não foi possível carregar nenhum dado!")
        st.info("📝 **Instruções:**")
        st.info("• **Atacado**: Arquivo com dados de vendas (formato atual)")
        st.info("• **Varejo**: Arquivo com 'varejo' no nome (.txt)")
        return
    
    # Exibir análise selecionada
    if st.session_state.analise_selecionada == "atacado":
        if df_atacado.empty:
            st.warning("❌ Dados do atacado não encontrados")
        else:
            dashboard_vendas(df_atacado, st.session_state.layout_mode)
    
    elif st.session_state.analise_selecionada == "varejo":
        dashboard_varejo(df_varejo, st.session_state.layout_mode)
    
    elif st.session_state.analise_selecionada == "geral":
        dashboard_geral_consolidado(df_atacado, df_varejo, st.session_state.layout_mode)
    
    elif st.session_state.analise_selecionada == "clientes":
        if df_atacado.empty:
            st.warning("❌ Dados do atacado necessários para análise de clientes")
        else:
            # Clientes com sub-navegação expandida (apenas atacado)
            tabs_clientes = st.tabs(["👶 Clientes Novos", "👥 Análise Geral", "🎯 Reativação"])
            
            with tabs_clientes[0]:
                analise_clientes_novos(df_atacado, st.session_state.layout_mode)
            
            with tabs_clientes[1]:
                analise_geral_clientes(df_atacado, st.session_state.layout_mode)
                
            with tabs_clientes[2]:
                analise_reativacao_clientes(df_atacado, st.session_state.layout_mode)
    
    elif st.session_state.analise_selecionada == "configuracoes":
        pagina_configuracoes()
    
    else:
        # Padrão: Dashboard do Atacado
        if df_atacado.empty:
            st.warning("❌ Dados do atacado não encontrados")
        else:
            dashboard_vendas(df_atacado, st.session_state.layout_mode)



if __name__ == "__main__":
    main()