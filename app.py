import pandas as pd

df = pd.read_excel('shop/Datas.xlsx', sheet_name='Products')

print(df.columns)
