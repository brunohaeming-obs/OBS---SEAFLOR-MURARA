import duckdb
import pandas as pd
import numpy as np
from pathlib import Path

GOLD = r"c:\Users\bruno.haeming\Desktop\Demandas\OBS - SEAFLOR MURARA\referencia\Dados\gold\comexstat_ncm_sc.parquet"
OUT  = Path(r"c:\Users\bruno.haeming\Desktop\Demandas\OBS - SEAFLOR MURARA\data\processed")


def gini(values):
    arr = np.array(sorted(values), dtype=float)
    n = len(arr)
    if n == 0 or arr.sum() == 0:
        return None
    idx = np.arange(1, n + 1)
    return (2 * (idx * arr).sum()) / (n * arr.sum()) - (n + 1) / n


SETORES = {
    "Madeira (CNAE 16)": "cd_cgce_n3 = '16'",
    "Moveis (CNAE 31)": "cd_cgce_n3 = '31'",
    "Base Florestal (CNAE 2)": "cd_cgce_n3 = '2'",
    "Papel e Celulose (CNAE 17)": "cd_cgce_n3 = '17'",
}

con = duckdb.connect()
resultados = []
lorenz_rows = []

for setor, filtro in SETORES.items():
    for ano in [2024, 2025]:
        df = con.execute(f"""
            SELECT ds_pais, SUM(vl_fob) AS vl_fob
            FROM read_parquet('{GOLD}')
            WHERE tp_carga='EXP' AND nr_ano={ano}
              AND {filtro}
              AND ds_pais IS NOT NULL
            GROUP BY ds_pais
            ORDER BY vl_fob DESC
        """).fetchdf()

        if df.empty:
            continue

        total = df["vl_fob"].sum()
        n_paises = len(df)
        g = gini(df["vl_fob"].values)
        top1_share = df.iloc[0]["vl_fob"] / total * 100
        top3_share = df.head(3)["vl_fob"].sum() / total * 100
        top5_share = df.head(5)["vl_fob"].sum() / total * 100
        top1_pais = df.iloc[0]["ds_pais"]
        shares = df["vl_fob"] / total
        hhi = (shares ** 2).sum() * 10000

        resultados.append({
            "Setor": setor,
            "Ano": ano,
            "Gini": round(g, 4),
            "Nº Países": n_paises,
            "Exportacoes Totais (US$)": round(total, 0),
            "HHI": round(hhi, 0),
            "1º País": top1_pais,
            "Share 1º País (%)": round(top1_share, 1),
            "Share Top 3 (%)": round(top3_share, 1),
            "Share Top 5 (%)": round(top5_share, 1),
        })

        vals_sorted = np.sort(df["vl_fob"].values)
        cum_pop = np.arange(1, n_paises + 1) / n_paises * 100
        cum_val = np.cumsum(vals_sorted) / total * 100
        step = max(1, n_paises // 20)
        for pop, val in zip(cum_pop[::step], cum_val[::step]):
            lorenz_rows.append({
                "Setor": setor,
                "Ano": ano,
                "% Países acumulado": round(pop, 1),
                "% Exportações acumulado": round(val, 1),
            })
        # garante ponto final (100, 100)
        lorenz_rows.append({"Setor": setor, "Ano": ano, "% Países acumulado": 100.0, "% Exportações acumulado": 100.0})

con.close()

res_df = pd.DataFrame(resultados)
lorenz_df = pd.DataFrame(lorenz_rows).drop_duplicates()

print("=== GINI ===")
print(res_df.to_string(index=False))

print("\n=== VARIAÇÃO GINI 2024 → 2025 ===")
pivot = res_df.pivot(index="Setor", columns="Ano", values="Gini")
pivot["Variação"] = (pivot[2025] - pivot[2024]).round(4)
print(pivot.to_string())

res_df.to_csv(OUT / "_gini_resultado.csv", index=False)
lorenz_df.to_csv(OUT / "_gini_lorenz.csv", index=False)
print("\nCSVs salvos.")
