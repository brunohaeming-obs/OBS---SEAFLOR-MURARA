import duckdb, pandas as pd

con = duckdb.connect()

NCM_DICT = r"referencia\Dados\silver\DICT\NCM_SH4 - atualizado 07.04.2026.xlsx"
PAIS_CSV = r"referencia\Dados\silver\DICT\PAIS.csv"
BRONZE_EXP = r"referencia\Dados\bronze\EXP\EXP_2026.csv"
GOLD_SC = r"referencia\Dados\gold\comexstat_ncm_sc.parquet"

ncm_df = pd.read_excel(NCM_DICT, dtype=str)
ncm_df.columns = [c.strip() for c in ncm_df.columns]
cod_col = [c for c in ncm_df.columns if "NCM" in c.upper() and "8" in c][0]
ncm_df = ncm_df.rename(columns={
    cod_col: "cd_ncm", "SC Competitiva": "sc_competitiva",
    "CNAE divisão": "cd_cgce_n3", "NO_NCM_POR": "ds_produto",
})
ncm_df["cd_ncm"] = ncm_df["cd_ncm"].astype(str).str.strip()
con.register("ncm_dim", ncm_df)

pais_df = pd.read_csv(PAIS_CSV, sep=";", encoding="latin-1", dtype=str)
pais_df.columns = [c.strip() for c in pais_df.columns]
pais_df = pais_df.rename(columns={"CO_PAIS": "co_pais", "NO_PAIS": "ds_pais"})
pais_df["co_pais"] = pais_df["co_pais"].astype(str).str.strip()
con.register("pais_dim", pais_df)

# Verificar valores únicos de sc_competitiva e cd_cgce_n3 no NCM dict
print("Valores únicos de sc_competitiva no NCM dict (Base Florestal / CNAE 2):")
r = con.execute("""
    SELECT DISTINCT sc_competitiva, cd_cgce_n3
    FROM ncm_dim
    WHERE cd_cgce_n3 = '2' OR sc_competitiva ILIKE '%florestal%'
    ORDER BY cd_cgce_n3
""").fetchdf()
print(r.to_string(index=False))
print()

# Verificar no gold parquet
print("Valores únicos no gold parquet (cd_cgce_n3 = '2'):")
r2 = con.execute(f"""
    SELECT DISTINCT sc_competitiva, cd_cgce_n3
    FROM read_parquet('{GOLD_SC}')
    WHERE cd_cgce_n3 = '2'
    LIMIT 5
""").fetchdf()
print(r2.to_string(index=False))
print()

# Verificar view 2026 para CNAE 2
print("Amostra v2026 para NCMs de sc_competitiva florestal:")
con.execute(f"""
CREATE OR REPLACE VIEW v2026 AS
WITH raw AS (
    SELECT CAST(CO_ANO AS INTEGER) AS nr_ano, CAST(CO_MES AS INTEGER) AS nr_mes,
           CAST(CO_NCM AS VARCHAR) AS cd_ncm, CAST(CO_PAIS AS VARCHAR) AS co_pais,
           CAST(SG_UF_NCM AS VARCHAR) AS sg_uf, CAST(VL_FOB AS DOUBLE) AS vl_fob,
           CAST(KG_LIQUIDO AS DOUBLE) AS qt_kilo_liquido, 'EXP' AS tp_carga
    FROM read_csv_auto('{BRONZE_EXP}', sep=';', ignore_errors=true)
    WHERE CAST(CO_MES AS INTEGER) <= 5
)
SELECT r.*, COALESCE(n.sc_competitiva,'Outros') AS sc_competitiva,
       COALESCE(CAST(n.cd_cgce_n3 AS VARCHAR),'') AS cd_cgce_n3,
       COALESCE(n.ds_produto, r.cd_ncm) AS ds_produto,
       COALESCE(p.ds_pais, 'Outros') AS ds_pais
FROM raw r
LEFT JOIN ncm_dim n ON r.cd_ncm = n.cd_ncm
LEFT JOIN pais_dim p ON r.co_pais = p.co_pais
""")

r3 = con.execute("""
    SELECT DISTINCT sc_competitiva, cd_cgce_n3, COUNT(*) AS n
    FROM v2026
    WHERE sg_uf='SC' AND sc_competitiva NOT IN ('Outros','')
    GROUP BY sc_competitiva, cd_cgce_n3
    ORDER BY n DESC
    LIMIT 20
""").fetchdf()
print(r3.to_string(index=False))
