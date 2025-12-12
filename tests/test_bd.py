import pandas as pd

data = pd.read_csv("/Users/rodionduktanov/anaconda_projects/RAG_Caspian_Analysis/ЦК(25.06.25)/pars_test.csv")

for x in data.columns: 
    print(x)

