# Dados Comex

Fluxo local para:

1. baixar ou atualizar os CSVs anuais no bronze
2. reconstruir o gold compatível com o relatório
3. gerar o Excel final a partir do template

O notebook [comex_pipeline_v1.ipynb](c:\Users\matheus.manzke\Projetos\dados-comex\Notebooks\comex_pipeline_v1.ipynb) continua útil para exploração, mas o caminho operacional agora é via CLI.

## Entradas e saídas

- Bronze: `Dados/bronze/EXP/*.csv` e `Dados/bronze/IMP/*.csv`
- Estado do bronze: `Dados/manifests/bronze_state.csv`
- Manifesto do bronze: `Dados/manifests/bronze_manifest.csv`
- Gold consolidado: `Dados/gold/comexstat_ncm_all.parquet`
- Gold SC: `Dados/gold/comexstat_ncm_sc.parquet`
- Template do relatório: `Dados/reports/Template - Comex Imprensa.xlsx`
- Relatório final: `Dados/reports/comex_report_sc.xlsx`

## Comandos principais

Use o Python do ambiente local:

```powershell
..\.venv\Scripts\python.exe main.py monthly
```

Esse comando faz o fluxo mensal completo:

1. bronze incremental
2. merge incremental do gold apenas para os anos afetados
3. geração do relatório final a partir do template

Backfill completo:

```powershell
..\.venv\Scripts\python.exe main.py backfill --start-year 1997
```

Somente gold:

```powershell
..\.venv\Scripts\python.exe main.py gold --start-year 2025 --end-year 2026 --incremental-merge
```

Somente relatório:

```powershell
..\.venv\Scripts\python.exe main.py report
```

## Validação de inconsistências

Para auditar uma divergência entre a fonte ComexStat, bronze, gold e relatório:

```powershell
.\venv\Scripts\python.exe Scripts\validate_report_data.py --kind EXP --year 2025 --month 1
```

Opções úteis:

```powershell
.\venv\Scripts\python.exe Scripts\validate_report_data.py --kind IMP --year 2025 --month 9 --uf SC --ncm 12345678
.\venv\Scripts\python.exe Scripts\validate_report_data.py --kind EXP --year 2025 --month 9 --report-path "Dados\reports\comex_report_sc.xlsx"
```

O auditor grava os resultados em `Dados/audit/validation_*`, com um `validation_report.md` e CSVs por sprint:

1. mapa do pipeline usado
2. totais da fonte bronze
3. integridade do bronze
4. impacto da normalização/dedupe
5. comparação gold e gold SC
6. agregação por produto no relatório
7. valores extraídos do Excel
8. resumo de causa provável

## Opções úteis

Incremental com janela de segurança:

```powershell
..\.venv\Scripts\python.exe main.py monthly --lookback-years 1
```

Ignorar verificação SSL no bronze, se necessário:

```powershell
..\.venv\Scripts\python.exe main.py monthly --no-verify
```

Template e saída customizados:

```powershell
..\.venv\Scripts\python.exe main.py report --template-path "Dados\\reports\\Template - Comex Imprensa.xlsx" --report-output "Dados\\reports\\comex_custom.xlsx"
```

## Estrutura operacional

- [bronze_ingest.py](c:\Users\matheus.manzke\Projetos\dados-comex\Scripts\bronze_ingest.py)
  faz o download incremental dos CSVs anuais e mantém `bronze_state.csv`
- [build_gold_report_compatible.py](c:\Users\matheus.manzke\Projetos\dados-comex\Scripts\build_gold_report_compatible.py)
  lê os CSVs do bronze e gera o gold no schema compatível com o relatório
- [run_pipeline.py](c:\Users\matheus.manzke\Projetos\dados-comex\Scripts\run_pipeline.py)
  orquestra bronze, gold e relatório
- [main.py](c:\Users\matheus.manzke\Projetos\dados-comex\main.py)
  é o ponto de entrada simples

## Observação

A renderização do Excel usa a lógica local em `pipeline-src`. Se essa pasta não existir, o runner ainda tenta usar o repo vizinho legado em:

`..\pipeline-relatorio-comex\src`
