# 📁 Nova Estrutura Organizacional - Grãos S.A.

A partir de agora, os dados estão organizados em pastas para melhor gestão e controle das atualizações diárias.

## 🗂️ Estrutura de Pastas

```
Clientes/
├── 📂 dados_historicos/          # Dados base até 25/07/2025
│   ├── Vendas até 25-07-2025.txt  (Atacado histórico)
│   ├── Varejo julho até dia 25.txt (Varejo histórico)
│   └── README.md
├── 📂 dados_diarios/             # Dados organizados por data
│   ├── 📁 2025-07-25/           # Dados do dia 25/07/2025
│   │   └── hoje-25-07-2025.txt
│   ├── 📁 2025-07-26/           # Dados do dia 26/07/2025
│   │   ├── Hoje 26-07-atacado.txt
│   │   ├── Hoje 26-07-varejo.txt
│   │   ├── Vendas até 26-07-2025.txt (consolidado)
│   │   └── varejo_ate_26072025.txt (consolidado)
│   ├── 📁 2025-07-28/           # Exemplo para próximas atualizações
│   │   └── EXEMPLO.txt
│   └── README.md
├── 📂 backups/                   # Arquivos de backup automáticos
│   ├── backup_atacado_AAAAMMDD_HHMMSS.txt
│   ├── backup_varejo_AAAAMMDD_HHMMSS.txt
│   └── README.md
├── analise_clientes_novos.py     # Sistema principal
├── requirements.txt
├── README.md
└── ESTRUTURA_ORGANIZACIONAL.md  # Este arquivo
```

## 🔄 Fluxo de Atualização Diária

### 1. **Preparação dos Dados**
Para cada novo dia (exemplo: 29/07/2025):
- Exporte os dados de **ATACADO** do sistema
- Exporte os dados de **VAREJO** do sistema
- Nomeie os arquivos como:
  - `atacado-29-07-2025.txt`
  - `varejo-29-07-2025.txt`

### 2. **Upload no Dashboard**
1. Acesse **"Gestão de Dados e Configurações"**
2. Use os uploaders separados:
   - **Upload Atacado**: para arquivo de atacado
   - **Upload Varejo**: para arquivo de varejo
3. O sistema automaticamente:
   - Cria pasta `dados_diarios/2025-07-29/`
   - Salva os arquivos na pasta correta
   - Faz backup dos dados anteriores
   - Integra com dados históricos

### 3. **Resultado Automático**
Após o upload, a pasta do dia conterá:
```
2025-07-29/
├── atacado-29-07-2025.txt      # Dados do dia
├── varejo-29-07-2025.txt       # Dados do dia
├── Vendas até 29-07-2025.txt   # Dados consolidados atacado
└── varejo_ate_29072025.txt     # Dados consolidados varejo
```

## ✅ Vantagens da Nova Estrutura

1. **📅 Organização Temporal**: Cada dia tem sua própria pasta
2. **🔒 Segurança**: Backups automáticos preservam dados anteriores
3. **📊 Rastreabilidade**: Histórico completo de todas as atualizações
4. **🚀 Performance**: Sistema otimizado para encontrar dados mais recentes
5. **🛠️ Manutenção**: Fácil identificação e correção de problemas

## 🎯 Compatibilidade

O sistema mantém **total compatibilidade** com:
- Arquivos existentes na raiz (fallback automático)
- Estrutura anterior de dados
- Todos os dashboards e funcionalidades

## 📝 Nomenclatura Padrão

### Arquivos Diários:
- **Atacado**: `atacado-DD-MM-AAAA.txt`
- **Varejo**: `varejo-DD-MM-AAAA.txt`

### Arquivos Consolidados:
- **Atacado**: `Vendas até DD-MM-AAAA.txt`
- **Varejo**: `varejo_ate_DDMMAAAA.txt`

### Backups:
- **Formato**: `backup_[tipo]_AAAAMMDD_HHMMSS.txt`
- **Local**: Pasta `backups/`

## 🚨 Importante

- **NUNCA** mova arquivos manualmente entre pastas
- **SEMPRE** use o sistema de upload do dashboard
- **MANTENHA** a nomenclatura padrão dos arquivos
- **VERIFIQUE** os dashboards após cada atualização

---

## 📞 Suporte

Em caso de dúvidas ou problemas:
1. Verifique se os arquivos estão nas pastas corretas
2. Consulte os arquivos README.md de cada pasta
3. Use a função de backup para restaurar dados se necessário

**Sistema atualizado em: 28/07/2025** 