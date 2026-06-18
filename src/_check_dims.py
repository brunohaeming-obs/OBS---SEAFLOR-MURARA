import duckdb, pandas as pd

con = duckdb.connect()

# País
pais = pd.read_csv(
    r"referencia\Dados\silver\DICT\PAIS.csv", sep=";", encoding="latin-1"
)
print("PAIS colunas:", list(pais.columns))
print(pais.head(3).to_string())
print()

# NCM
ncm = pd.read_excel(
    r"referencia\Dados\silver\DICT\NCM_SH4 - atualizado 07.04.2026.xlsx"
)
print("NCM colunas:", list(ncm.columns))
print(ncm.head(3).to_string())
print()

# Confirmar que gold SC tem 2025 Jan-Mai
r = con.execute("""
    SELECT nr_ano, nr_mes, COUNT(*) AS n, SUM(vl_fob) AS fob
    FROM read_parquet('referencia/Dados/gold/comexstat_ncm_sc.parquet')
    WHERE tp_carga='EXP' AND nr_ano=2025 AND nr_mes<=5
    GROUP BY nr_ano, nr_mes ORDER BY nr_mes
""").fetchdf()
print("SC gold 2025 Jan-Mai EXP:")
print(r.to_string(index=False))
