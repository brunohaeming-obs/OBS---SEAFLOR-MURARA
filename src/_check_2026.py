import duckdb
con = duckdb.connect()

for tp in ['EXP', 'IMP']:
    f = rf'referencia\Dados\bronze\{tp}\{tp}_2026.csv'
    cols = con.execute(f"SELECT * FROM read_csv_auto('{f}', sep=';') LIMIT 1").description
    print(f'{tp}_2026 colunas:', [c[0] for c in cols])
    r = con.execute(f"""
        SELECT CO_MES, COUNT(*) AS n, SUM(VL_FOB) AS fob
        FROM read_csv_auto('{f}', sep=';')
        WHERE CAST(CO_MES AS INTEGER) <= 5
        GROUP BY CO_MES ORDER BY CO_MES
    """).fetchdf()
    print(r.to_string(index=False))
    print()
