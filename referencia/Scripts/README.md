Armazene aqui os scripts (.py) definitivos, ou seja, que geram dados, resultados e modelos.

Se existir um ordem de execução é importante informar pelo próprio nome do arquivo. Exemplo:

- Extração: ingestão de dados, coleta de api, banco de dados...
- Processamento: limpezas, transformações, engenheria de dados...
- Modelagem: testes com diferentes modelos, avaliação de desempenho e validação, modelos treinados (`.pkl`, `.joblib`, `.h5`) que serão salvos no diretório Modelos. 

```
├── Scripts/
    ├── Extracao
    │   └── 1_coleta_bases.py
    ├── Processamento
    │   └── 2_prep_bases.py
    └── Modelagem
        └── 3_ML_classif.py
```