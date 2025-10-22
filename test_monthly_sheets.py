#!/usr/bin/env python3
"""
Teste rápido das funcionalidades de abas mensais.
"""
import os
import sys
from datetime import datetime, date
from pathlib import Path

# Adiciona o diretório app ao path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from config import config
from sheets import GoogleSheetsManager

def test_monthly_sheets():
    """Testa a criação de abas mensais."""
    print("🧪 Testando funcionalidades de abas mensais...")
    
    try:
        # Inicializa o manager
        manager = GoogleSheetsManager()
        print("✅ GoogleSheetsManager inicializado")
        
        # Testa nome da aba do mês
        mes_nome = manager._get_month_worksheet_name()
        print(f"📅 Aba do mês atual: {mes_nome}")
        
        # Testa se é aba de mês
        is_month = manager._is_month_worksheet("2025-10")
        print(f"✅ '2025-10' é aba de mês: {is_month}")
        
        is_not_month = manager._is_month_worksheet("usuarios")
        print(f"❌ 'usuarios' é aba de mês: {is_not_month}")
        
        # Testa conexão
        connection_ok = manager.test_connection()
        print(f"🌐 Conexão Google Sheets: {'✅ OK' if connection_ok else '❌ Erro'}")
        
        print("🎉 Testes concluídos com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro durante os testes: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_monthly_sheets()