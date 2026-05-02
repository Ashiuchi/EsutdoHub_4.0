import sqlite3
import pandas as pd
import os
from datetime import datetime

DB_PATH = "dev.db"

def run_audit():
    print(f"--- RELATÓRIO DE STATUS MOENDA (RAIZ) ({datetime.now().strftime('%d/%m/%Y %H:%M')}) ---\n")
    
    if not os.path.exists(DB_PATH):
        print(f"Erro: Arquivo {DB_PATH} não encontrado.")
        return
            
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # 1. Status Geral de Editais
        df_editais = pd.read_sql_query("SELECT status, count(*) as total FROM editais GROUP BY status", conn)
        print("ESTADO DOS EDITAIS:")
        print(df_editais.to_string(index=False))
        
        # 2. Status de Cargos
        df_cargos = pd.read_sql_query("SELECT status, count(*) as total FROM cargos GROUP BY status", conn)
        print("\nESTADO DOS CARGOS:")
        print(df_cargos.to_string(index=False))
        
        # 3. Extração de Matérias
        total_cargos = pd.read_sql_query("SELECT count(*) as total FROM cargos", conn).iloc[0]['total']
        cargos_com_materias = pd.read_sql_query("SELECT count(distinct cargo_id) as total FROM materias", conn).iloc[0]['total']
        
        print(f"\nCargos Totais: {total_cargos}")
        print(f"Cargos com Matérias: {cargos_com_materias} ({ (cargos_com_materias/total_cargos*100 if total_cargos > 0 else 0):.1f}%)")
        
        # 4. Topicos
        total_topicos = pd.read_sql_query("SELECT count(*) as total FROM topicos", conn).iloc[0]['total']
        print(f"Tópicos Atomizados: {total_topicos}")
        
        conn.close()
    except Exception as e:
        print(f"Erro ao acessar banco: {e}")

if __name__ == "__main__":
    run_audit()
