# Dados Diários

Esta pasta contém os dados organizados por data. Cada subpasta representa um dia específico com os dados de vendas correspondentes.

## Estrutura
```
dados_diarios/
├── 2025-07-25/
│   └── hoje-25-07-2025.txt (dados do dia 25/07)
├── 2025-07-26/
│   ├── Hoje 26-07-atacado.txt (vendas atacado do dia 26/07)
│   ├── Hoje 26-07-varejo.txt (vendas varejo do dia 26/07)
│   ├── Vendas até 26-07-2025.txt (dados atacado consolidados até 26/07)
│   └── varejo_ate_26072025.txt (dados varejo consolidados até 26/07)
└── 2025-07-28/ (exemplo para próximas atualizações)
```

## Como usar
1. **Para cada novo dia**, crie uma pasta no formato `AAAA-MM-DD`
2. **Adicione os arquivos** de vendas do dia:
   - `atacado-DD-MM-AAAA.txt` (vendas atacado do dia)
   - `varejo-DD-MM-AAAA.txt` (vendas varejo do dia)
3. **Após processamento**, os arquivos consolidados também ficam na mesma pasta

## Exemplo para hoje (28/07/2025)
Criar pasta: `2025-07-28/`
Adicionar arquivos:
- `atacado-28-07-2025.txt`
- `varejo-28-07-2025.txt` 