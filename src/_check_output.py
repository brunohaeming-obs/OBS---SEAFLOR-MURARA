import pandas as pd

xl = pd.ExcelFile('data/processed/SEAFLOR_2026_JanMai_2025vs2026.xlsx')

# Título na linha 0, cabeçalhos na linha 1, dados a partir da linha 2
def ler(aba):
    return pd.read_excel(xl, sheet_name=aba, header=1)

df = ler('1_Resumo_Geral')
print("=== Colunas Resumo ===")
print(list(df.columns))
print()
print(df[['Setor','EXP_USD_2025','EXP_USD_2026','Var_EXP_USD_Pct']].to_string(index=False))
print()

df2 = ler('2_Mensal_Total')
print("=== Mensal Total ===")
print(df2.to_string(index=False))
print()

df3 = ler('6_Concentracao_EUA')
print("=== Share EUA ===")
print(df3[['Mes_Nome','Share_EUA_2025_Pct','Share_EUA_2026_Pct','Var_Share_EUA_pp']].to_string(index=False))
