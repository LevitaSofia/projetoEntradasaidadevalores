"""
Gerenciador de uploads para Google Drive.
Salva comprovantes (imagens e PDFs) e retorna links públicos.
"""
import logging
import io
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError

from .config import config
from .models import TZ_BRASIL

logger = logging.getLogger(__name__)


class DriveManagerError(Exception):
    """Erro específico do gerenciador do Drive."""
    pass


class GoogleDriveManager:
    """
    Gerenciador para uploads no Google Drive.
    Salva comprovantes e gera links compartilháveis.
    """
    
    def __init__(self):
        """Inicializa cliente Google Drive."""
        self._service = None
        self._folder_id = None
        self._setup_drive()
    
    def _setup_drive(self) -> None:
        """Configura acesso ao Google Drive."""
        try:
            # Configura credenciais
            scopes = [
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/drive"
            ]
            
            creds = Credentials.from_service_account_info(
                config.google_service_account_json,
                scopes=scopes
            )
            
            # Inicializa serviço
            self._service = build('drive', 'v3', credentials=creds)
            
            # Cria/encontra pasta para comprovantes
            self._setup_comprovantes_folder()
            
            logger.info("Google Drive configurado com sucesso")
            
        except Exception as e:
            error_msg = f"Erro ao configurar Google Drive: {e}"
            logger.error(error_msg)
            raise DriveManagerError(error_msg)
    
    def _setup_comprovantes_folder(self) -> None:
        """Cria ou encontra a pasta 'Comprovantes Bot' no Drive."""
        try:
            folder_name = "Comprovantes Bot Financeiro"
            
            # Busca pasta existente
            results = self._service.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'",
                fields="files(id, name)"
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                # Usa pasta existente
                self._folder_id = folders[0]['id']
                logger.info(f"Usando pasta existente: {folder_name}")
            else:
                # Cria nova pasta
                folder_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                
                folder = self._service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                
                self._folder_id = folder.get('id')
                logger.info(f"Pasta criada: {folder_name}")
                
        except Exception as e:
            logger.error(f"Erro ao configurar pasta de comprovantes: {e}")
            self._folder_id = None
    
    def upload_comprovante(
        self,
        file_data: bytes,
        filename: str,
        mime_type: str,
        chat_id: int,
        descricao: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Faz upload de um comprovante para o Google Drive.
        
        Args:
            file_data: Dados do arquivo em bytes
            filename: Nome do arquivo
            mime_type: Tipo MIME do arquivo
            chat_id: ID do chat do usuário
            descricao: Descrição opcional do comprovante
            
        Returns:
            Tuple[str, str]: (file_id, public_link)
        """
        try:
            # Gera nome único para o arquivo
            timestamp = datetime.now(TZ_BRASIL).strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{chat_id}_{filename}"
            
            # Metadados do arquivo
            file_metadata = {
                'name': unique_filename,
                'parents': [self._folder_id] if self._folder_id else []
            }
            
            if descricao:
                file_metadata['description'] = f"Comprovante: {descricao}"
            
            # Upload do arquivo
            media = MediaIoBaseUpload(
                io.BytesIO(file_data),
                mimetype=mime_type,
                resumable=True
            )
            
            file = self._service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            
            # Torna o arquivo público
            self._service.permissions().create(
                fileId=file_id,
                body={
                    'role': 'reader',
                    'type': 'anyone'
                }
            ).execute()
            
            # Gera link público
            public_link = f"https://drive.google.com/file/d/{file_id}/view"
            
            logger.info(f"Comprovante salvo: {unique_filename} - {public_link}")
            
            return file_id, public_link
            
        except HttpError as e:
            error_msg = f"Erro da API Google Drive: {e}"
            logger.error(error_msg)
            raise DriveManagerError(error_msg)
        except Exception as e:
            error_msg = f"Erro ao fazer upload do comprovante: {e}"
            logger.error(error_msg)
            raise DriveManagerError(error_msg)
    
    def delete_comprovante(self, file_id: str) -> bool:
        """
        Remove um comprovante do Google Drive.
        
        Args:
            file_id: ID do arquivo no Drive
            
        Returns:
            bool: True se removido com sucesso
        """
        try:
            self._service.files().delete(fileId=file_id).execute()
            logger.info(f"Comprovante removido: {file_id}")
            return True
            
        except HttpError as e:
            logger.error(f"Erro ao remover comprovante {file_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro geral ao remover comprovante {file_id}: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        Testa conectividade com Google Drive.
        
        Returns:
            bool: True se conexão ok, False caso contrário
        """
        try:
            # Tenta listar arquivos para testar conexão
            results = self._service.files().list(pageSize=1).execute()
            logger.info("Teste de conexão Google Drive OK")
            return True
        except Exception as e:
            logger.error(f"Erro no teste de conexão Google Drive: {e}")
            return False


# Instância global do gerenciador
drive_manager = GoogleDriveManager()