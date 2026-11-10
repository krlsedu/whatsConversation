#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WhatsApp Media Processor & Timeline Builder (CscTracker Ecosystem)
Suporta:
1. Modo Banco Local (Método 2 - Sem Limites / 8+ Anos):
   Lê diretamente o msgstore.db (descriptografado do msgstore.db.crypt15 via ADB + chave 64 dígitos),
   localiza os áudios em WhatsApp Voice Notes / WhatsApp Audio, copia os áudios da conversa para uma
   pasta dedicada no diretório corrente, transcreve via CscTracker AI BFF (https://bff.csctracker.com/ai-processor/analyze)
   seguindo o padrão hardcoded do CscTrackerVigilante (model='lite', thinking_level='minimal', task='transcrição de audio do whats')
   e gera a conversa formatada (DD/MM/YYYY HH:MM:SS - Nome: Mensagem) + PDF estruturado.
2. Modo ZIP Exportado (Método 1 - Legado):
   Processa arquivos .zip exportados pelo WhatsApp, transcrevendo áudios "(arquivo anexado)" e gerando TXT + PDF.
"""

import argparse
import base64
import datetime
import html
import json
import os
import re
import shutil
import sqlite3
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests


def analyze(
    prompt_texto: str,
    file_base64: str,
    mime_type: str,
    event_id: str,
    token: str,
) -> Optional[str]:
    """
    Chamada direta ao CscTracker AI hardcoded como no CscTrackerVigilante:
    model='lite', thinking_level='minimal', force_paid=True, return_json=False.
    """
    _body = {
        "prompt": prompt_texto,
        "input_text": "",
        "base64": file_base64,
        "mime_type": mime_type,
        "model": "lite",
        "return_json": False,
        "task": "Transcrição de audio",
        "force_paid": True,
        "event_id": event_id,
        "thinking_level": "minimal",
    }

    _headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        _response = requests.post(
            "https://bff.csctracker.com/ai-processor/analyze",
            json=_body,
            headers=_headers,
            timeout=6000,
        )
        if not (200 <= _response.status_code < 300):
            print(f"[{event_id}] Erro HTTP {_response.status_code} no CscTracker AI: {_response.text}")
            return None

        try:
            _resp_json = _response.json()
            if isinstance(_resp_json, dict):
                return _resp_json.get("response")
            return str(_resp_json)
        except json.JSONDecodeError:
            return _response.text
    except Exception as e:
        print(f"[{event_id}] Erro na chamada ao CscTracker AI: {e}")
        return None


class WhatsAppMediaProcessor:
    def __init__(
        self,
        zip_path: Optional[str] = None,
        token_csctracker: Optional[str] = None,
        enable_resume: bool = True,
        db_path: Optional[str] = None,
        media_dir: Optional[str] = None,
        phone_filter: Optional[str] = None,
        contact_name: str = "Suelen Boff",
        my_name: str = "Carlos Eduardo",
        work_dir: Optional[str] = None,
    ):
        self.zip_path = Path(zip_path) if zip_path else None
        self.db_path = Path(db_path) if db_path else None
        self.media_dir = Path(media_dir) if media_dir else None
        self.phone_filter = phone_filter
        self.contact_name = contact_name
        self.my_name = my_name
        self.work_dir = Path(work_dir) if work_dir else (Path.cwd() / "dados_whatsapp")

        self.media_files: List[str] = []
        self.audio_files: List[Path] = []
        self.audio_index_by_name: Dict[str, Path] = {}
        self.conversation_file: Optional[str] = None
        self.token_csctracker = token_csctracker or os.getenv("TOKEN_CSCTRACKER")
        self.extract_dir: Optional[Path] = None
        self.checkpoint_file: Optional[Path] = None
        self.transcribed_files: Set[str] = set()
        self.transcriptions_map: Dict[str, str] = {}
        self.enable_resume = enable_resume

    # ==========================================================================
    # MODO 2: EXTRAÇÃO DIRETA DO BANCO SQLITE (msgstore.db) + PASTA DE ÁUDIOS ADB
    # ==========================================================================
    def _locate_chat_id(self, conn: sqlite3.Connection, phone_or_name: str) -> Tuple[int, str]:
        cur = conn.cursor()
        clean_term = re.sub(r"[\s\-\+\(\)]", "", phone_or_name.strip())

        if clean_term:
            cur.execute(
                """
                SELECT c._id, j.raw_string, c.subject
                FROM chat c
                JOIN jid j ON c.jid_row_id = j._id
                WHERE j.raw_string LIKE ? OR c.subject LIKE ?
                ORDER BY c._id ASC
                """,
                (f"%{clean_term}%", f"%{phone_or_name.strip()}%"),
            )
            rows = cur.fetchall()
            if rows:
                return rows[0][0], rows[0][1]

        cur.execute(
            """
            SELECT c._id, j.raw_string, COUNT(m._id) as total_msgs
            FROM chat c
            JOIN jid j ON c.jid_row_id = j._id
            LEFT JOIN message m ON m.chat_row_id = c._id
            GROUP BY c._id, j.raw_string
            ORDER BY total_msgs DESC
            LIMIT 15
            """
        )
        top_chats = cur.fetchall()
        dica = "\n".join([f"  - JID: {r[1]} ({r[2]} mensagens)" for r in top_chats])
        raise ValueError(
            f"Nenhum chat encontrado para o filtro '{phone_or_name}'.\n"
            f"Principais conversas encontradas neste msgstore.db:\n{dica}"
        )

    def _index_media_directory(self, root_dir: Path):
        """Indexa todos os arquivos de áudio dentro da pasta extraída via ADB para busca O(1)."""
        if not root_dir or not root_dir.exists():
            return
        audio_extensions = {".mp3", ".aac", ".ogg", ".opus", ".m4a", ".wav"}
        for p in root_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in audio_extensions:
                self.audio_index_by_name[p.name] = p

    def _resolve_audio_path(self, media_root: Optional[Path], rel_file_path: Optional[str]) -> Optional[Path]:
        if not rel_file_path:
            return None
        clean_rel = rel_file_path.replace("\\", "/").lstrip("/")
        filename = Path(clean_rel).name

        if media_root and media_root.exists():
            parts = clean_rel.split("/")
            without_media = "/".join(parts[1:]) if parts and parts[0].lower() == "media" else clean_rel
            for candidate in (media_root / without_media, media_root / clean_rel):
                if candidate.exists():
                    return candidate

        return self.audio_index_by_name.get(filename)

    def extract_from_sqlite_db(self) -> Tuple[str, List[str]]:
        """
        Extrai 100% da conversa (todos os anos) a partir do msgstore.db, copia os áudios
        da conversa para uma pasta dedicada no diretório corrente e gera o arquivo base .txt
        no padrão:
            DD/MM/YYYY HH:MM:SS - Suelen Boff: mensagem
            DD/MM/YYYY HH:MM:SS - Carlos Eduardo: nome_audio.opus (arquivo anexado)
        """
        if not self.db_path or not self.db_path.exists():
            raise FileNotFoundError(f"Banco SQLite msgstore.db não encontrado em: {self.db_path}")

        self.extract_dir = self.work_dir / "conversa_extraida"
        audios_dest_dir = self.extract_dir / "audios_conversa"
        self.extract_dir.mkdir(parents=True, exist_ok=True)
        audios_dest_dir.mkdir(parents=True, exist_ok=True)

        if self.media_dir and self.media_dir.exists():
            print(f"Indexando pasta de áudios ({self.media_dir})...")
            self._index_media_directory(self.media_dir)

        conn = sqlite3.connect(str(self.db_path))
        search_key = self.phone_filter if self.phone_filter else self.contact_name
        chat_id, jid_str = self._locate_chat_id(conn, search_key)
        print(f"Conversa localizada no SQLite: chat_id={chat_id} | JID={jid_str}")

        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                m._id AS msg_id,
                m.from_me,
                m.timestamp,
                m.message_type,
                m.text_data,
                mm.file_path,
                mm.media_duration,
                mm.mime_type
            FROM message m
            LEFT JOIN message_media mm ON mm.message_row_id = m._id
            WHERE m.chat_row_id = ?
            ORDER BY m.timestamp ASC, m._id ASC
            """,
            (chat_id,),
        )

        lines: List[str] = []
        self.audio_files = []
        self.media_files = []
        seen_audio_names: Set[str] = set()

        for row in cur.fetchall():
            msg_id, from_me, ts_ms, msg_type, text_data, file_path, duration, mime_type = row
            if not ts_ms:
                continue

            dt_str = datetime.datetime.fromtimestamp(ts_ms / 1000.0).strftime("%d/%m/%Y %H:%M:%S")
            sender = self.my_name if from_me == 1 else self.contact_name
            clean_text = str(text_data).strip() if text_data else ""

            is_audio = (
                (msg_type == 2)
                or (mime_type and str(mime_type).lower().startswith("audio/"))
                or (
                    file_path
                    and any(
                        ext in str(file_path).lower()
                        for ext in [".opus", ".ogg", ".mp3", ".aac", ".m4a", "voice notes", "whatsapp audio"]
                    )
                )
            )

            if is_audio:
                orig_name = Path(str(file_path).replace("\\", "/")).name if file_path else f"audio_{msg_id}.opus"
                if Path(orig_name).suffix.lower() not in {".opus", ".ogg", ".mp3", ".aac"}:
                    orig_name = f"{orig_name}.opus"

                ts_prefix = datetime.datetime.fromtimestamp(ts_ms / 1000.0).strftime("%Y%m%d_%H%M%S")
                unique_audio_name = f"{ts_prefix}_{msg_id}_{orig_name}"
                dest_audio_path = audios_dest_dir / unique_audio_name

                src_audio = self._resolve_audio_path(self.media_dir, file_path)
                if src_audio and src_audio.exists():
                    if not dest_audio_path.exists():
                        shutil.copy2(src_audio, dest_audio_path)
                    if unique_audio_name not in seen_audio_names:
                        self.audio_files.append(dest_audio_path)
                        seen_audio_names.add(unique_audio_name)

                lines.append(f"{dt_str} - {sender}: {unique_audio_name} (arquivo anexado)")
                if clean_text:
                    lines.append(f"{dt_str} - {sender}: {clean_text}")

            elif clean_text:
                lines.append(f"{dt_str} - {sender}: {clean_text}")

        conn.close()

        conv_txt_path = self.extract_dir / "conversa_completa.txt"
        with open(conv_txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        self.conversation_file = str(conv_txt_path)
        return self.conversation_file, self.media_files

    # ==========================================================================
    # MODO 1: EXTRAÇÃO DE ARQUIVO .ZIP EXPORTADO PELO WHATSAPP
    # ==========================================================================
    def extract_and_analyze_zip(self) -> Tuple[str, List[str]]:
        if not self.zip_path or not self.zip_path.exists():
            raise FileNotFoundError(f"ZIP file not found: {self.zip_path}")

        self.extract_dir = self.zip_path.parent / f"{self.zip_path.stem}_extracted"
        self.extract_dir.mkdir(exist_ok=True)

        with zipfile.ZipFile(self.zip_path, "r") as zip_ref:
            zip_ref.extractall(self.extract_dir)

        txt_files = [p for p in self.extract_dir.glob("*.txt") if not p.name.endswith("_processed.txt")]
        if not txt_files:
            raise FileNotFoundError("No conversation text file found in ZIP")

        self.conversation_file = str(txt_files[0])

        audio_extensions = {".mp3", ".aac", ".ogg", ".opus"}
        other_media_extensions = {".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov", ".3gp", ".pdf", ".doc", ".docx"}
        all_media_extensions = audio_extensions | other_media_extensions

        self.media_files = []
        self.audio_files = []

        for file_path in self.extract_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in all_media_extensions:
                if file_path.suffix.lower() in audio_extensions:
                    self.audio_files.append(file_path)
                    self.audio_index_by_name[file_path.name] = file_path
                else:
                    self.media_files.append(file_path.name)

        return self.conversation_file, self.media_files

    # ==========================================================================
    # CHECKPOINT & SPEECH-TO-TEXT VIA CSCTRACKER AI (PADRÃO VIGILANTE)
    # ==========================================================================
    def _setup_checkpoint_file(self):
        if self.extract_dir:
            self.checkpoint_file = self.extract_dir / "transcription_checkpoint.json"

    def _load_checkpoint(self) -> Set[str]:
        if not self.checkpoint_file or not self.checkpoint_file.exists():
            return set()
        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.transcriptions_map = data.get("transcriptions", {})
                return set(data.get("transcribed_files", []))
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load checkpoint file: {e}")
            return set()

    def _save_checkpoint(self, transcribed_file: str, transcription_text: str):
        if not self.checkpoint_file:
            return
        self.transcribed_files.add(transcribed_file)
        self.transcriptions_map[transcribed_file] = transcription_text
        try:
            checkpoint_data = {
                "transcribed_files": sorted(list(self.transcribed_files)),
                "transcriptions": self.transcriptions_map,
                "last_updated": datetime.datetime.now().isoformat(),
            }
            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Warning: Could not save checkpoint: {e}")

    @staticmethod
    def _resolve_audio_mime_type(audio_file_path: Path) -> str:
        ext = audio_file_path.suffix.lower()
        mime_map = {
            ".opus": "audio/ogg",
            ".ogg": "audio/ogg",
            ".mp3": "audio/mp3",
            ".aac": "audio/aac",
            ".m4a": "audio/mp4",
            ".wav": "audio/wav",
        }
        return mime_map.get(ext, "audio/ogg")

    @staticmethod
    def _clean_transcription_text(raw_text: str) -> str:
        """Expurga preâmbulos e reflexões de raciocínio (thinking) gerados pela IA."""
        if not raw_text:
            return ""
        text = raw_text.strip()
        text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"get_audio_duration\(\).*?(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕ\"0-9]|$)", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"^.*?the audio duration is.*?(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕ\"0-9]|$)", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"^(?:Using context|Transcription rule|Audio language|Unintelligible rule).*?\n+", "", text, flags=re.MULTILINE | re.IGNORECASE)
        if "\n\n" in text and any(k in text for k in ["00:", "timestamp", "duration"]):
            parts = [p.strip() for p in text.split("\n\n") if p.strip()]
            if len(parts) > 1 and not re.search(r"^\d{2}:\d{2}", parts[-1]):
                text = parts[-1]
        text = re.sub(r"^[\"']|[\"']$", "", text.strip())
        return text.strip()

    def transcribe_audio(self, audio_file_path: Path) -> Tuple[str, bool]:
        """
        Envia o áudio codificado em Base64 para https://bff.csctracker.com/ai-processor/analyze
        utilizando TOKEN_CSCTRACKER, model='lite', thinking_level='minimal' e task='transcrição de audio do whats'.
        """
        if not self.token_csctracker:
            return f"[ÁUDIO: {audio_file_path.name} - TOKEN_CSCTRACKER não configurado]", False

        try:
            audio_bytes = audio_file_path.read_bytes()
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            mime_type = self._resolve_audio_mime_type(audio_file_path)

            prompt = (
                "Por favor, transcreva este arquivo de áudio em português brasileiro. "
                "Forneça apenas a transcrição do texto falado, sem comentários adicionais. "
                "Se não conseguir entender partes do áudio, indique com [inaudível]."
            )

            response_text = analyze(
                prompt_texto=prompt,
                file_base64=audio_b64,
                mime_type=mime_type,
                event_id=audio_file_path.name,
                token=self.token_csctracker,
            )

            transcription = self._clean_transcription_text(str(response_text)) if response_text else ""
            if transcription:
                return f"[ÁUDIO: {audio_file_path.name}] Transcrição: {transcription}", True
            return f"[ÁUDIO: {audio_file_path.name} - não foi possível transcrever]", False
        except Exception as e:
            return f"[ÁUDIO: {audio_file_path.name} - erro: {str(e)}]", False

    def process_conversation_file(self) -> str:
        if not self.conversation_file or not os.path.exists(self.conversation_file):
            raise FileNotFoundError("Conversation file not found")

        self._setup_checkpoint_file()
        output_file = self.conversation_file.replace(".txt", "_processed.txt")

        if not self.enable_resume:
            print("Resume disabled. Starting fresh transcription...")
            if self.checkpoint_file and self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
            if os.path.exists(output_file):
                os.remove(output_file)
            self.transcribed_files = set()
            self.transcriptions_map = {}
        else:
            self.transcribed_files = self._load_checkpoint()

        with open(self.conversation_file, "r", encoding="utf-8") as f:
            content = f.read()

        media_pattern = r"([^\s]+\.(opus|mp3|aac|ogg|mp4|jpg|jpeg|png|gif|mov|3gp|pdf|doc|docx))\s*\(arquivo anexado\)"
        media_matches = list(re.finditer(media_pattern, content, re.IGNORECASE))

        print(f"Total de anexos referenciados na conversa: {len(media_matches)}")
        print(f"Total de arquivos de áudio disponíveis no disco: {len(self.audio_files)}")

        audio_lookup: Dict[str, Path] = {af.name: af for af in self.audio_files}
        lines = content.split("\n")
        processed_lines: List[str] = []
        audio_extensions = {".opus", ".mp3", ".aac", ".ogg"}
        transcriptions_added = 0
        restored_from_checkpoint = 0

        for line in lines:
            processed_lines.append(line)
            match = re.search(media_pattern, line, re.IGNORECASE)
            if not match:
                continue

            filename = match.group(1)
            file_extension = Path(filename).suffix.lower()
            if file_extension not in audio_extensions:
                continue

            clean_filename = filename.replace("\u200e", "").replace("\u200f", "").strip()

            if clean_filename in self.transcribed_files and clean_filename in self.transcriptions_map:
                cached_text = self.transcriptions_map[clean_filename]
                processed_lines.append(f"📝 {cached_text}")
                restored_from_checkpoint += 1
                continue

            audio_file_path = audio_lookup.get(clean_filename) or self.audio_index_by_name.get(clean_filename)

            if audio_file_path and audio_file_path.exists() and self.token_csctracker:
                print(f"Transcrevendo áudio via CscTracker AI: {clean_filename}...")
                transcription, ok = self.transcribe_audio(audio_file_path)
                processed_lines.append(f"📝 {transcription}")
                if ok:
                    transcriptions_added += 1
                    self._save_checkpoint(clean_filename, transcription)

                with open(output_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(processed_lines))

            elif audio_file_path and audio_file_path.exists():
                msg = f"[ÁUDIO: {clean_filename} - aguardando TOKEN_CSCTRACKER para transcrever]"
                processed_lines.append(f"📝 {msg}")
            else:
                msg = f"[ÁUDIO: {clean_filename} - arquivo de áudio não encontrado na pasta de mídia]"
                processed_lines.append(f"📝 {msg}")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(processed_lines))

        print(f"Conversa processada salva em: {output_file}")
        if restored_from_checkpoint > 0:
            print(f"Transcrições recuperadas do checkpoint: {restored_from_checkpoint}")
        print(f"Novas transcrições via CscTracker AI nesta execução: {transcriptions_added}")
        return output_file

    # ==========================================================================
    # GERAÇÃO DE PDF ESTRUTURADO DA CONVERSA (LINHA DO TEMPO VISUAL)
    # ==========================================================================
    def generate_structured_pdf(self, processed_txt_path: str, pdf_output_path: Optional[str] = None) -> str:
        """
        Gera um PDF estruturado e elegante a partir do arquivo de conversa processado.
        """
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        txt_path = Path(processed_txt_path)
        if not pdf_output_path:
            pdf_output_path = str(txt_path.with_suffix(".pdf"))

        with open(txt_path, "r", encoding="utf-8") as f:
            raw_lines = [l.rstrip("\r") for l in f.readlines() if l.strip()]

        doc = SimpleDocTemplate(
            pdf_output_path,
            pagesize=A4,
            leftMargin=14 * mm,
            rightMargin=14 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
            title=f"Linha do Tempo — {self.contact_name} & {self.my_name}",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#475569"),
            spaceAfter=12,
        )
        day_header_style = ParagraphStyle(
            "DayHeader",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#1E3A8A"),
            spaceBefore=10,
            spaceAfter=6,
        )
        sender_suelen_style = ParagraphStyle(
            "SenderSuelen",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#9D174D"),
        )
        sender_carlos_style = ParagraphStyle(
            "SenderCarlos",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#0369A1"),
        )
        body_style = ParagraphStyle(
            "MsgBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor("#1E293B"),
        )
        audio_style = ParagraphStyle(
            "AudioTrans",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#065F46"),
        )

        story = [
            Paragraph(f"Histórico Completo de Conversa — {html.escape(self.contact_name)} &amp; {html.escape(self.my_name)}", title_style),
            Paragraph(
                f"Gerado em {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')} • Textos e transcrições de áudio em ordem cronológica",
                subtitle_style,
            ),
        ]

        msg_regex = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}(?::\d{2})?)\s+-\s+([^:]+):\s*(.*)$")

        current_date = None
        pending_cards: List[Tuple[str, str, str, List[str]]] = []

        for line in raw_lines:
            m = msg_regex.match(line)
            if m:
                d_str, t_str, author, msg_text = m.group(1), m.group(2), m.group(3).strip(), m.group(4).strip()
                pending_cards.append((d_str, t_str, author, [msg_text]))
            elif line.startswith("📝") and pending_cards:
                pending_cards[-1][3].append(line)
            elif pending_cards:
                pending_cards[-1][3].append(line)

        usable_width = A4[0] - 28 * mm

        for d_str, t_str, author, msg_parts in pending_cards:
            if d_str != current_date:
                current_date = d_str
                story.append(Paragraph(f"📅 {html.escape(current_date)}", day_header_style))

            is_carlos = self.my_name.lower() in author.lower() or "carlos" in author.lower()
            header_style = sender_carlos_style if is_carlos else sender_suelen_style
            bg_color = colors.HexColor("#F0F9FF") if is_carlos else colors.HexColor("#FDF2F8")
            border_color = colors.HexColor("#BAE6FD") if is_carlos else colors.HexColor("#FBCFE8")

            cell_Flowables = [
                Paragraph(f"{html.escape(author)}  •  <font color='#64748B'>{html.escape(d_str)} às {html.escape(t_str)}</font>", header_style),
                Spacer(1, 2),
            ]

            for part in msg_parts:
                safe_part = html.escape(part).replace("\n", "<br/>")
                if part.startswith("📝"):
                    cell_Flowables.append(Paragraph(safe_part, audio_style))
                else:
                    cell_Flowables.append(Paragraph(safe_part, body_style))

            tbl = Table([[cell_Flowables]], colWidths=[usable_width])
            tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), bg_color),
                        ("BOX", (0, 0), (-1, -1), 0.6, border_color),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(tbl)
            story.append(Spacer(1, 4))

        doc.build(story)
        print(f"PDF estruturado gerado com sucesso em: {pdf_output_path}")
        return pdf_output_path

    def get_summary(self) -> Dict[str, int]:
        if not self.conversation_file or not os.path.exists(self.conversation_file):
            return {}
        with open(self.conversation_file, "r", encoding="utf-8") as f:
            content = f.read()

        media_pattern = r"([^\s]+\.(opus|mp3|aac|ogg|mp4|jpg|jpeg|png|gif|mov|3gp|pdf|doc|docx))\s*\(arquivo anexado\)"
        media_matches = len(re.findall(media_pattern, content, re.IGNORECASE))

        audio_pattern = r"([^\s]+\.(opus|mp3|aac|ogg))\s*\(arquivo anexado\)"
        audio_matches = len(re.findall(audio_pattern, content, re.IGNORECASE))

        return {
            "media_entries_found": media_matches,
            "audio_entries_found": audio_matches,
            "media_files_found": len(self.media_files),
            "audio_files_found": len(self.audio_files),
            "total_media_files": len(self.media_files) + len(self.audio_files),
            "transcriptions_possible": min(audio_matches, len(self.audio_files)),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Processador de Conversas e Transcrição de Áudios do WhatsApp via CscTracker AI (Modo SQLite msgstore.db ou Modo ZIP)."
    )
    parser.add_argument("zip_file", nargs="?", default=None, help="Caminho para o arquivo .zip exportado (opcional se usar --db)")
    parser.add_argument("--db", help="Caminho para o banco SQLite msgstore.db descriptografado (Método 2)")
    parser.add_argument("--media-dir", help="Pasta raiz contendo WhatsApp Voice Notes e WhatsApp Audio extraídos via ADB")
    parser.add_argument("--phone", help="Dígitos do telefone ou nome para localizar a conversa no msgstore.db")
    parser.add_argument("--contact-name", default="Suelen Boff", help="Nome de exibição do contato (padrão: Suelen Boff)")
    parser.add_argument("--my-name", default="Carlos Eduardo", help="Seu nome de exibição (padrão: Carlos Eduardo)")
    parser.add_argument("--work-dir", default=None, help="Diretório de trabalho (padrão: ./dados_whatsapp no diretório corrente)")
    parser.add_argument("--pdf", action="store_true", default=True, help="Gera PDF estruturado ao final (ativo por padrão)")
    parser.add_argument("--no-pdf", action="store_true", help="Desativa a geração do PDF")
    parser.add_argument("--verbose", "-v", action="store_true", help="Ativa saída detalhada")
    parser.add_argument("--token-csctracker", help="Token Bearer do CscTracker (ou use a variável de ambiente TOKEN_CSCTRACKER)")
    parser.add_argument("--resume", action="store_true", help="Continua de onde parou usando o checkpoint (padrão)")
    parser.add_argument("--no-resume", action="store_true", help="Força início do zero ignorando o checkpoint")

    args = parser.parse_args()
    token_csctracker = args.token_csctracker or os.getenv("TOKEN_CSCTRACKER")

    if not token_csctracker:
        print("Aviso: TOKEN_CSCTRACKER não informado. Os áudios serão listados na linha do tempo, mas não transcritos.")

    enable_resume = not args.no_resume

    try:
        processor = WhatsAppMediaProcessor(
            zip_path=args.zip_file,
            token_csctracker=token_csctracker,
            enable_resume=enable_resume,
            db_path=args.db,
            media_dir=args.media_dir,
            phone_filter=args.phone,
            contact_name=args.contact_name,
            my_name=args.my_name,
            work_dir=args.work_dir,
        )

        if args.db:
            conversation_file, _ = processor.extract_from_sqlite_db()
        elif args.zip_file:
            conversation_file, _ = processor.extract_and_analyze_zip()
        else:
            default_db = Path.cwd() / "dados_whatsapp" / "msgstore.db"
            default_media = Path.cwd() / "dados_whatsapp" / "raw_android"
            if default_db.exists():
                processor.db_path = default_db
                if not processor.media_dir and default_media.exists():
                    processor.media_dir = default_media
                conversation_file, _ = processor.extract_from_sqlite_db()
            else:
                parser.error("Informe um arquivo .zip ou use --db apontando para o msgstore.db (ou execute exportar_whatsapp_adb.ps1).")
                return 1

        output_file = processor.process_conversation_file()

        pdf_file = None
        if args.pdf and not args.no_pdf:
            try:
                pdf_file = processor.generate_structured_pdf(output_file)
            except Exception as pdf_err:
                print(f"Aviso ao gerar PDF: {pdf_err}")

        summary = processor.get_summary()
        print("\n=== RESUMO DO PROCESSAMENTO ===")
        print(f"Anexos na conversa:       {summary.get('media_entries_found', 0)}")
        print(f"Áudios na conversa:       {summary.get('audio_entries_found', 0)}")
        print(f"Arquivos de áudio locais: {len(processor.audio_files)}")
        print(f"Arquivo TXT processado:   {output_file}")
        if pdf_file:
            print(f"Arquivo PDF estruturado:  {pdf_file}")

    except Exception as e:
        print(f"Erro: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())