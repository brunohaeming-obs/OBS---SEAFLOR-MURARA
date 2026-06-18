import pandas as pd
xl = pd.ExcelFile('data/processed/SEAFLOR_2026_JanMai_2025vs2026_v2.xlsx')

eua = pd.read_excel(xl, '6_Conc_EUA', header=1)
print("=== Share EUA ===")
print(eua[['Mes_Nome','EXP_EUA_2025','EXP_EUA_2026','Share_EUA_2025_Pct','Share_EUA_2026_Pct','Var_Share_EUA_pp']].to_string(index=False))
print()

r = pd.read_excel(xl, '1_Resumo_Geral', header=1)
print("=== Resumo Jan-Mai ===")
print(r[['Setor','EXP_USD_2025','EXP_USD_2026','Var_EXP_USD_Pct','Nr_Destinos_2025','Nr_Destinos_2026']].to_string(index=False))
print()

h = pd.read_excel(xl, '10_HHI_Gini', header=1)
print("=== HHI / Gini ===")
print(h[['Setor','HHI_2024','HHI_2025','HHI_2026','Gini_2024','Gini_2025','Gini_2026']].to_string(index=False))
print()

t = eua[eua['Mes_Nome']=='TOTAL Jan-Mai'].iloc[0]
perda = t['EXP_EUA_2025'] - t['EXP_EUA_2026']
print(f"Perda EXP para EUA Jan-Mai: US$ {perda:,.0f}")

s = pd.read_excel(xl, '12_Share_Pais', header=1)
print()
print("=== Ganhadores / Perdedores ===")
print(s[['Pais','Share_2024_Pct','Share_2025_Pct','Share_2026_Pct','Var_Share_25_26_pp','Ganhou_Perdeu_25_26']].head(12).to_string(index=False))
