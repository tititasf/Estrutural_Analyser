import imaplib
import email
import os
import datetime
from email.header import decode_header
from PySide6.QtCore import QObject, Signal, QThread
import logging

class EmailService(QObject):
    """
    Serviço para gerenciar sincronização de e-mails via IMAP.
    Executa em uma thread separada para não bloquear a UI.
    """
    new_email_received = Signal(dict)
    sync_started = Signal()
    sync_finished = Signal(int) # Retorna quantidade de novos emails
    error_occurred = Signal(str)

    def __init__(self, email_user, email_pass, imap_server="imap.gmail.com"):
        super().__init__()
        self.email_user = email_user
        self.email_pass = email_pass
        self.imap_server = imap_server
        self.is_connected = False
        self._is_running = False

    def connect(self):
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server)
            self.mail.login(self.email_user, self.email_pass)
            self.is_connected = True
            logging.info(f"✅ EmailService conectado como {self.email_user}")
            return True
        except Exception as e:
            self.error_occurred.emit(f"Faha na conexão IMAP: {e}")
            logging.error(f"❌ Erro EmailService: {e}")
            return False

    def fetch_emails(self, folder="INBOX", limit=20):
        """Busca emails recentes com reconexão automática."""
        try:
            if not self.is_connected:
                if not self.connect():
                    return
            
            # Tenta selecionar a pasta. Se falhar (conexão caiu), reconecta.
            try:
                self.mail.select(folder)
            except (imaplib.IMAP4.error, OSError, Exception) as e:
                logging.warning(f"⚠️ Conexão IMAP perdida ({e}). Reconectando...")
                self.is_connected = False
                if not self.connect():
                    return
                self.mail.select(folder)

            self.sync_started.emit()
            count_new = 0

            # Busca todos os emails
            status, messages = self.mail.search(None, "ALL")
            
            if not messages or not messages[0]:
                 self.sync_finished.emit(0)
                 return

            email_ids = messages[0].split()
            recent_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids

            for e_id in reversed(recent_ids):
                # Fetch headers only first for optimization (future) - here getting full for simplicity of proto
                res, msg_data = self.mail.fetch(e_id, "(RFC822)")
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        parsed_email = self._parse_email(msg)
                        
                        # Filtro básico de exemplo (pode ser hardcoded "PROJETO" como pedido)
                        if self._is_relevant(parsed_email):
                            self.new_email_received.emit(parsed_email)
                            count_new += 1
            
            self.sync_finished.emit(count_new)
            
        except Exception as e:
            self.error_occurred.emit(f"Erro ao buscar emails: {e}")
            logging.error(f"Erro CRÍTICO fetch_emails: {e}")
            self.is_connected = False # Força reconexão na próxima tentativa

    def _parse_email(self, msg):
        """Extrai dados relevantes do email."""
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding if encoding else "utf-8")
            
        from_ = msg.get("From")
        date_ = msg.get("Date")
        
        body = ""
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        # Decode filename if needed
                        fname, fenc = decode_header(filename)[0]
                        if isinstance(fname, bytes):
                            filename = fname.decode(fenc if fenc else "utf-8")
                        
                        file_data = part.get_payload(decode=True)
                        # Encode to base64 string for JSON serialization
                        import base64
                        b64_data = base64.b64encode(file_data).decode('utf-8') if file_data else None
                        
                        attachments.append({
                            "name": filename,
                            "size": len(file_data) if file_data else 0,
                            "data": b64_data 
                        })
                elif content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body_bytes = part.get_payload(decode=True)
                        body = body_bytes.decode() 
                    except: pass
        else:
            try:
                body = msg.get_payload(decode=True).decode()
            except: pass

        # DRIVE LINK DETECTION
        try:
            import re
            # Regex to find Google Drive file links
            drive_regex = r"https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)"
            matches = re.finditer(drive_regex, body)
            
            for match in matches:
                file_id = match.group(1)
                direct_link = f"https://drive.usercontent.google.com/u/0/uc?id={file_id}&export=download"
                
                # Check if already added to avoid duplicates if regex matches multiple times
                if not any(att.get('drive_id') == file_id for att in attachments):
                    attachments.append({
                        "name": f"Drive_File_{file_id[-6:]}.pdf", # Generic name guess, user can rename
                        "size": 0, # Unknowable without request
                        "data": None,
                        "drive_id": file_id,
                        "drive_link": direct_link,
                        "original_link": match.group(0),
                        "type": "drive_link"
                    })
        except Exception as e:
            logging.warning(f"Erro ao parsear links do Drive: {e}")

        return {
            "subject": subject,
            "sender": from_,
            "date": date_,
            "body": body,
            "attachments": attachments
        }

    def _is_relevant(self, email_data):
        """
        Filtra emails relevantes. 
        Agora retorna True para tudo, pois a filtragem é por cliente no DB.
        Ou pode manter um filtro minimo.
        """
        # User requested: "se for do email de qualquer cliente ou qualquer usuario da equipe sim deve reconhecer"
        # We process ALL and filter in UI/DB logic to map to clients.
        return True

class EmailSyncThread(QThread):
    """Wrapper para rodar o fetch em background."""
    def __init__(self, service):
        super().__init__()
        self.service = service
    
    def run(self):
        self.service.fetch_emails()
