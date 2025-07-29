#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise Temporal - Julho 2025
Script independente para análise de vendas diárias
"""

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import os

def detectar_coluna_data(df):
    """Detecta coluna de data no DataFrame"""
    opcoes = ['Data Competência', 'Data CompetÃªncia', df.columns[0]]
    for col in opcoes:
        if col in df.columns:
            return col
    return df.columns[0]

def detectar_coluna_valor(df):
    """Detecta coluna de valor no DataFrame"""
    opcoes = ['Total Venda', 'Total_Venda', 'Valor_Liquido']
    for col in opcoes:
        if col in df.columns:
            return col
    return df.columns[14] if len(df.columns) > 14 else df.columns[10]

def carregar_dados():
    """Carrega dados do atacado e varejo"""
    try:
        # Atacado
        df_atacado = pd.read_csv('dados_diarios/2025-07-28/Vendas até 28-07-2025.txt', 
                                sep=';', encoding='latin-1')
        # Varejo
        df_varejo = pd.read_csv('dados_diarios/2025-07-28/varejo_ate_28072025.txt', 
                               sep=';', encoding='utf-8')
        return df_atacado, df_varejo
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return None, None

def processar_dados_julho(df, nome_setor):
    """Processa dados para julho 2025"""
    if df is None or df.empty:
        return None
    
    try:
        # Detectar colunas
        col_data = detectar_coluna_data(df)
        col_valor = detectar_coluna_valor(df)
        
        # Processar datas
        df['Data_dt'] = pd.to_datetime(df[col_data], format='%d/%m/%Y', errors='coerce')
        
        # Filtrar julho 2025
        mask_julho = (df['Data_dt'].dt.month == 7) & (df['Data_dt'].dt.year == 2025)
        df_julho = df[mask_julho].copy()
        
        if df_julho.empty:
            st.warning(f"❌ Nenhum dado de {nome_setor} para julho 2025")
            return None
        
        # Processar valores
        df_julho['Valor_Clean'] = df_julho[col_valor].astype(str).str.replace(',', '.').astype(float)
        
        # Agrupar por dia
        resultado = df_julho.groupby(df_julho['Data_dt'].dt.date).agg({
            'Valor_Clean': 'sum',
            col_data: 'count'  # Quantidade de vendas
        }).reset_index()
        
        resultado.columns = ['Data', f'Faturamento_{nome_setor}', f'Qtd_Vendas_{nome_setor}']
        
        st.success(f"✅ {nome_setor}: {len(resultado)} dias processados")
        return resultado
        
    except Exception as e:
        st.error(f"❌ Erro ao processar {nome_setor}: {e}")
        return None

def main():
    st.set_page_config(page_title="Análise Temporal - Julho 2025", layout="wide")
    
    st.title("📅 Análise Temporal - Julho 2025")
    st.caption("*Vendas diárias separadas por setor*")
    
    # Carregar dados
    with st.spinner("Carregando dados..."):
        df_atacado, df_varejo = carregar_dados()
    
    if df_atacado is None and df_varejo is None:
        st.error("❌ Não foi possível carregar nenhum dado")
        return
    
    # Processar dados
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏢 Processando Atacado")
        dados_atacado = processar_dados_julho(df_atacado, 'Atacado')
    
    with col2:
        st.subheader("🏪 Processando Varejo")
        dados_varejo = processar_dados_julho(df_varejo, 'Varejo')
    
    # Consolidar dados
    if dados_atacado is not None or dados_varejo is not None:
        
        # Merge dos dados
        if dados_atacado is not None and dados_varejo is not None:
            df_final = pd.merge(dados_atacado, dados_varejo, on='Data', how='outer')
        elif dados_atacado is not None:
            df_final = dados_atacado.copy()
            df_final['Faturamento_Varejo'] = 0
            df_final['Qtd_Vendas_Varejo'] = 0
        else:
            df_final = dados_varejo.copy()
            df_final['Faturamento_Atacado'] = 0
            df_final['Qtd_Vendas_Atacado'] = 0
        
        # Preencher NaNs
        df_final = df_final.fillna(0)
        
        # Calcular totais
        df_final['Faturamento_Total'] = df_final.get('Faturamento_Atacado', 0) + df_final.get('Faturamento_Varejo', 0)
        df_final['Qtd_Vendas_Total'] = df_final.get('Qtd_Vendas_Atacado', 0) + df_final.get('Qtd_Vendas_Varejo', 0)
        
        # Ordenar por data
        df_final = df_final.sort_values('Data')
        
        # === GRÁFICOS ===
        st.markdown("---")
        st.subheader("📊 Análise Visual")
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=['💰 Faturamento Diário (R$)', '📈 Quantidade de Vendas'],
            vertical_spacing=0.12
        )
        
        # Faturamento
        if 'Faturamento_Atacado' in df_final.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_final['Data'],
                    y=df_final['Faturamento_Atacado'],
                    name='🏢 Atacado',
                    line=dict(color='#1f77b4', width=3),
                    mode='lines+markers'
                ),
                row=1, col=1
            )
        
        if 'Faturamento_Varejo' in df_final.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_final['Data'],
                    y=df_final['Faturamento_Varejo'],
                    name='🏪 Varejo',
                    line=dict(color='#ff7f0e', width=3),
                    mode='lines+markers'
                ),
                row=1, col=1
            )
        
        # Total
        fig.add_trace(
            go.Scatter(
                x=df_final['Data'],
                y=df_final['Faturamento_Total'],
                name='💰 Total',
                line=dict(color='#2ca02c', width=4, dash='dash'),
                mode='lines+markers'
            ),
            row=1, col=1
        )
        
        # Quantidade de vendas
        if 'Qtd_Vendas_Atacado' in df_final.columns:
            fig.add_trace(
                go.Bar(
                    x=df_final['Data'],
                    y=df_final['Qtd_Vendas_Atacado'],
                    name='📊 Vendas Atacado',
                    marker_color='rgba(31, 119, 180, 0.7)'
                ),
                row=2, col=1
            )
        
        if 'Qtd_Vendas_Varejo' in df_final.columns:
            fig.add_trace(
                go.Bar(
                    x=df_final['Data'],
                    y=df_final['Qtd_Vendas_Varejo'],
                    name='📊 Vendas Varejo',
                    marker_color='rgba(255, 127, 14, 0.7)'
                ),
                row=2, col=1
            )
        
        fig.update_layout(
            height=700,
            title_text="📅 Vendas Diárias - Julho 2025",
            showlegend=True,
            hovermode='x unified'
        )
        
        fig.update_yaxes(title_text="Faturamento (R$)", row=1, col=1)
        fig.update_yaxes(title_text="Quantidade de Vendas", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # === MÉTRICAS ===
        st.markdown("---")
        st.subheader("📈 Resumo do Mês")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_mes = df_final['Faturamento_Total'].sum()
            st.metric("💰 Total Julho", f"R$ {total_mes:,.2f}")
        
        with col2:
            media_diaria = df_final['Faturamento_Total'].mean()
            st.metric("📊 Média Diária", f"R$ {media_diaria:,.2f}")
        
        with col3:
            melhor_dia = df_final.loc[df_final['Faturamento_Total'].idxmax()]
            st.metric("🏆 Melhor Dia", f"{melhor_dia['Data'].strftime('%d/%m')}", 
                     f"R$ {melhor_dia['Faturamento_Total']:,.2f}")
        
        with col4:
            total_vendas = df_final['Qtd_Vendas_Total'].sum()
            st.metric("📈 Total Vendas", f"{total_vendas:.0f}")
        
        # === COMPARAÇÃO POR SETOR ===
        st.markdown("---")
        st.subheader("🔄 Comparação Atacado vs Varejo")
        
        col1, col2 = st.columns(2)
        
        with col1:
            total_atacado = df_final['Faturamento_Atacado'].sum()
            vendas_atacado = df_final['Qtd_Vendas_Atacado'].sum()
            st.info(f"""
            **🏢 ATACADO - JULHO 2025**
            - **Faturamento:** R$ {total_atacado:,.2f}
            - **Vendas:** {vendas_atacado:.0f}
            - **Ticket Médio:** R$ {total_atacado/max(1,vendas_atacado):,.2f}
            """)
        
        with col2:
            total_varejo = df_final['Faturamento_Varejo'].sum()
            vendas_varejo = df_final['Qtd_Vendas_Varejo'].sum()
            st.info(f"""
            **🏪 VAREJO - JULHO 2025**
            - **Faturamento:** R$ {total_varejo:,.2f}
            - **Vendas:** {vendas_varejo:.0f}
            - **Ticket Médio:** R$ {total_varejo/max(1,vendas_varejo):,.2f}
            """)
        
        # === PADRÕES SAZONAIS ===
        st.markdown("---")
        st.subheader("🔄 Padrões por Período do Mês")
        
        # Dividir julho em períodos
        df_final['Periodo'] = df_final['Data'].apply(lambda x: 
            'Início (1-10)' if x.day <= 10 else 
            'Meio (11-20)' if x.day <= 20 else 
            'Final (21-31)'
        )
        
        # Calcular médias por período
        stats_periodo = df_final.groupby('Periodo').agg({
            'Faturamento_Atacado': 'mean',
            'Faturamento_Varejo': 'mean',
            'Faturamento_Total': 'mean'
        }).round(2)
        
        col1, col2, col3 = st.columns(3)
        
        for idx, (periodo, stats) in enumerate(stats_periodo.iterrows()):
            with [col1, col2, col3][idx]:
                st.metric(
                    f"📅 {periodo}",
                    f"R$ {stats['Faturamento_Total']:,.2f}",
                    help=f"Atacado: R$ {stats['Faturamento_Atacado']:,.2f} | Varejo: R$ {stats['Faturamento_Varejo']:,.2f}"
                )
        
        # Insight sazonal
        if 'Início (1-10)' in stats_periodo.index and 'Final (21-31)' in stats_periodo.index:
            inicio = stats_periodo.loc['Início (1-10)', 'Faturamento_Total']
            final = stats_periodo.loc['Final (21-31)', 'Faturamento_Total']
            
            variacao = ((final - inicio) / inicio * 100) if inicio > 0 else 0
            
            if abs(variacao) > 20:
                if variacao < 0:
                    st.warning(f"⚠️ **Padrão**: Queda de {abs(variacao):.1f}% do início para o final do mês")
                else:
                    st.success(f"📈 **Padrão**: Crescimento de {variacao:.1f}% do início para o final do mês")
            else:
                st.info("📊 **Padrão**: Vendas relativamente estáveis ao longo do mês")
        
        # === TABELA DETALHADA ===
        if st.checkbox("📋 Ver dados detalhados por dia"):
            df_display = df_final.copy()
            df_display['Data'] = df_display['Data'].astype(str)
            df_display['Faturamento_Atacado'] = df_display['Faturamento_Atacado'].apply(lambda x: f"R$ {x:,.2f}")
            df_display['Faturamento_Varejo'] = df_display['Faturamento_Varejo'].apply(lambda x: f"R$ {x:,.2f}")
            df_display['Faturamento_Total'] = df_display['Faturamento_Total'].apply(lambda x: f"R$ {x:,.2f}")
            st.dataframe(df_display, use_container_width=True)
    
    else:
        st.error("❌ Nenhum dado válido encontrado para julho 2025")

if __name__ == "__main__":
    main() 