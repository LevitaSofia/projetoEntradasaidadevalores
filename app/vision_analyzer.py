"""
Analisador de comprovantes usando OpenAI Vision.
Analisa imagens de notas fiscais, recibos e extratos para extrair dados financeiros.
"""
import logging
import base64
from typing import Optional, Tuple
from io import BytesIO

from openai import OpenAI
from PIL import Image

from .config import config
from .models import LancamentoFinanceiro

logger = logging.getLogger(__name__)


class VisionAnalyzerError(Exception):
    """Erro específico do analisador de visão."""
    pass


class OpenAIVisionAnalyzer:
    """
    Analisador de comprovantes usando OpenAI Vision.
    Extrai dados financeiros de imagens de comprovantes.
    """
    
    def __init__(self):
        """Inicializa cliente OpenAI."""
        self._client = OpenAI(api_key=config.openai_api_key)
    
    def _encode_image_to_base64(self, image_data: bytes) -> str:
        """
        Converte dados de imagem para base64.
        
        Args:
            image_data: Dados da imagem em bytes
            
        Returns:
            str: Imagem codificada em base64
        """
        try:
            # Abre imagem para validar formato
            img = Image.open(BytesIO(image_data))
            
            # Redimensiona se muito grande (otimização)
            max_size = (1024, 1024)
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Salva imagem redimensionada
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                image_data = buffer.getvalue()
            
            # Codifica em base64
            return base64.b64encode(image_data).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Erro ao processar imagem: {e}")
            raise VisionAnalyzerError(f"Erro ao processar imagem: {e}")
    
    def analyze_receipt(
        self, 
        image_data: bytes, 
        user_context: Optional[str] = None
    ) -> Tuple[Optional[LancamentoFinanceiro], str]:
        """
        Analisa um comprovante/recibo e extrai dados financeiros.
        
        Args:
            image_data: Dados da imagem em bytes
            user_context: Contexto adicional do usuário (opcional)
            
        Returns:
            Tuple[Optional[LancamentoFinanceiro], str]: (lancamento_extraido, analise_detalhada)
        """
        try:
            # Codifica imagem
            base64_image = self._encode_image_to_base64(image_data)
            
            # Prepara prompt para análise
            system_prompt = self._get_analysis_prompt()
            
            user_prompt = "Analise este comprovante/recibo e extraia as informações financeiras."
            if user_context:
                user_prompt += f" Contexto adicional: {user_context}"
            
            # Chama OpenAI Vision
            response = self._client.chat.completions.create(
                model="gpt-4o-mini",  # Modelo com suporte a visão
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            analysis_text = response.choices[0].message.content
            
            # Tenta extrair lançamento estruturado
            lancamento = self._extract_structured_data(analysis_text)
            
            logger.info("Análise de comprovante concluída com sucesso")
            return lancamento, analysis_text
            
        except Exception as e:
            error_msg = f"Erro ao analisar comprovante: {e}"
            logger.error(error_msg)
            raise VisionAnalyzerError(error_msg)
    
    def _get_analysis_prompt(self) -> str:
        """Retorna o prompt para análise de comprovantes."""
        return """Você é um especialista em análise de comprovantes financeiros brasileiros.

Analise esta imagem de comprovante/recibo/nota fiscal e extraia:

1. TIPO: Se é uma entrada (recebimento, depósito, crédito) ou saída (pagamento, compra, débito)
2. VALOR: O valor principal da transação em reais (IMPORTANTE: use formato brasileiro com vírgula para decimais, ex: 750,00 ou 1.250,50)
3. DESCRIÇÃO: Descrição clara do que foi pago/recebido
4. CATEGORIA: Categoria da despesa/receita (alimentação, transporte, etc.)
5. DATA: Data da transação se visível

REGRAS IMPORTANTES:
- Para notas fiscais/cupons: sempre SAÍDA (compra)
- Para recibos de pagamento: SAÍDA
- Para comprovantes de depósito/PIX recebido: ENTRADA
- Se houver múltiplos valores, use o valor total/final
- VALORES: Use sempre formato brasileiro (vírgula para decimais), exemplos corretos:
  * R$ 750,00 (setecentos e cinquenta reais)
  * R$ 1.250,50 (mil duzentos e cinquenta reais e cinquenta centavos)
  * R$ 25,90 (vinte e cinco reais e noventa centavos)
- Se não conseguir identificar algo, indique "não identificado"

FORMATO DA RESPOSTA:
TIPO: [entrada/saída]
VALOR: [valor em reais com vírgula decimal]
DESCRIÇÃO: [descrição clara]
CATEGORIA: [categoria]
DATA: [data se visível]

ANÁLISE: [explicação detalhada do que foi identificado na imagem]"""
    
    def _extract_structured_data(self, analysis_text: str) -> Optional[LancamentoFinanceiro]:
        """
        Extrai dados estruturados da análise de texto.
        
        Args:
            analysis_text: Texto da análise da IA
            
        Returns:
            Optional[LancamentoFinanceiro]: Lançamento extraído ou None
        """
        try:
            lines = analysis_text.split('\n')
            extracted_data = {}
            
            for line in lines:
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().upper()
                    value = value.strip()
                    
                    if key in ['TIPO', 'VALOR', 'DESCRIÇÃO', 'DESCRICAO', 'CATEGORIA', 'DATA']:
                        extracted_data[key] = value
            
            # Verifica se temos dados mínimos
            if not all(k in extracted_data for k in ['TIPO', 'VALOR', 'DESCRIÇÃO']):
                logger.warning("Dados insuficientes extraídos da análise")
                return None
            
            # Normaliza tipo
            tipo = extracted_data['TIPO'].lower()
            if 'entrada' in tipo or 'receb' in tipo or 'credit' in tipo:
                tipo = 'entrada'
            else:
                tipo = 'saida'
            
            # Limpa valor com lógica brasileira
            valor_str = extracted_data['VALOR']
            valor_str = valor_str.replace('R$', '').strip()
            
            # Remove espaços e caracteres especiais
            import re
            
            # Se tem vírgula, assume formato brasileiro (ex: 1.750,50 ou 750,00)
            if ',' in valor_str:
                # Remove pontos (separador de milhares) e converte vírgula para ponto
                valor_str = valor_str.replace('.', '').replace(',', '.')
            else:
                # Se não tem vírgula, verifica se é formato americano (750.50) ou inteiro (750)
                partes = valor_str.split('.')
                if len(partes) == 2 and len(partes[1]) <= 2:
                    # Provavelmente formato americano (ex: 750.50)
                    pass  # mantém como está
                else:
                    # Remove pontos (separador de milhares)
                    valor_str = valor_str.replace('.', '')
            
            # Remove caracteres não numéricos exceto ponto decimal
            valor_str = re.sub(r'[^\d.]', '', valor_str)
            
            if not valor_str:
                logger.warning("Valor não identificado na análise")
                return None
            
            # Cria lançamento
            lancamento = LancamentoFinanceiro(
                tipo=tipo,
                valor=float(valor_str),
                descricao=extracted_data.get('DESCRIÇÃO', extracted_data.get('DESCRICAO', 'Comprovante analisado')),
                categoria=extracted_data.get('CATEGORIA', ''),
                data=extracted_data.get('DATA', 'today')
            )
            
            return lancamento
            
        except Exception as e:
            logger.warning(f"Erro ao extrair dados estruturados: {e}")
            return None
    
    def test_vision_api(self) -> bool:
        """
        Testa se a API de visão está funcionando.
        
        Returns:
            bool: True se funcionando, False caso contrário
        """
        try:
            # Cria uma imagem de teste simples
            test_image = Image.new('RGB', (100, 100), color='white')
            buffer = BytesIO()
            test_image.save(buffer, format='JPEG')
            test_data = buffer.getvalue()
            
            base64_image = base64.b64encode(test_data).decode('utf-8')
            
            response = self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Descreva esta imagem em uma palavra."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=10
            )
            
            logger.info("Teste da API de visão OK")
            return True
            
        except Exception as e:
            logger.error(f"Erro no teste da API de visão: {e}")
            return False


# Instância global do analisador
vision_analyzer = OpenAIVisionAnalyzer()