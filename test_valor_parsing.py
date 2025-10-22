"""
Script de teste para verificar o parsing de valores brasileiros.
"""
import re

def test_valor_parsing(valor_str_original):
    """Testa a lógica corrigida de parsing de valores."""
    print(f"\n🔍 Testando: '{valor_str_original}'")
    
    valor_str = valor_str_original.replace('R$', '').strip()
    
    # Remove espaços e caracteres especiais
    print(f"Após limpar R$: '{valor_str}'")
    
    # Se tem vírgula, assume formato brasileiro (ex: 1.750,50 ou 750,00)
    if ',' in valor_str:
        print("📍 Detectado formato brasileiro (com vírgula)")
        # Remove pontos (separador de milhares) e converte vírgula para ponto
        valor_str = valor_str.replace('.', '').replace(',', '.')
        print(f"Após conversão BR: '{valor_str}'")
    else:
        print("📍 Formato sem vírgula - verificando...")
        # Se não tem vírgula, verifica se é formato americano (750.50) ou inteiro (750)
        partes = valor_str.split('.')
        if len(partes) == 2 and len(partes[1]) <= 2:
            print("📍 Detectado formato americano (ex: 750.50)")
            # Provavelmente formato americano (ex: 750.50)
            pass  # mantém como está
        else:
            print("📍 Detectado número inteiro ou com separador de milhares")
            # Remove pontos (separador de milhares)
            valor_str = valor_str.replace('.', '')
    
    # Remove caracteres não numéricos exceto ponto decimal
    valor_str = re.sub(r'[^\d.]', '', valor_str)
    print(f"Valor final: '{valor_str}'")
    
    if valor_str:
        try:
            valor_float = float(valor_str)
            print(f"✅ Resultado: R$ {valor_float:.2f}")
            return valor_float
        except ValueError:
            print("❌ Erro ao converter para float")
            return None
    else:
        print("❌ Valor vazio após limpeza")
        return None

# Casos de teste
casos_teste = [
    "R$ 750,00",      # Caso original do problema
    "R$ 750.000,00",  # Formato que pode confundir
    "750,00",         # Sem R$
    "1.250,50",       # Com milhares
    "750.50",         # Formato americano
    "750",            # Inteiro
    "25,90",          # Centavos
    "1.500",          # Mil e quinhentos (sem centavos)
    "R$ 2.750,85",    # Caso completo
]

print("🧪 TESTE DE PARSING DE VALORES BRASILEIROS")
print("=" * 50)

for caso in casos_teste:
    test_valor_parsing(caso)

print("\n" + "=" * 50)
print("🎯 CASOS ESPECÍFICOS DE PROBLEMA:")
print("- '750,00' deve resultar em 750.0 (não 750000.0)")
print("- '1.750,50' deve resultar em 1750.5")
print("- '750.50' deve resultar em 750.5 (formato americano)")