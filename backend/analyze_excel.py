import pandas as pd
import sys

def analyze():
    try:
        # Tenta ler todas as abas
        excel_file = pd.ExcelFile('/app/static/images/planilha_estudos.xlsx')
        print(f"Abas encontradas: {excel_file.sheet_names}")
        
        for sheet in excel_file.sheet_names:
            print(f"\n--- ABA: {sheet} ---")
            df = pd.read_excel(excel_file, sheet_name=sheet)
            print(df.to_markdown())
            
    except Exception as e:
        print(f"Erro na análise: {e}")

if __name__ == '__main__':
    analyze()
