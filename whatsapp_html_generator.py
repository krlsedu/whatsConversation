#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WhatsApp Chat HTML Generator (CscTracker Ecosystem)

Gera um arquivo HTML com visual e comportamento idênticos ao WhatsApp Web a partir
do arquivo de conversa processado (conversa_completa_processed.txt).
- Exibe balões de conversa (enviados/recebidos) com nomes e horários.
- Miniaturas de imagens com clique para visualização ampliada (Lightbox) e legenda com a descrição da IA.
- Áudios com player integrado e caixa destacada para a transcrição.
- Divisores de data estilo WhatsApp.
- Totalmente standalone: HTML + CSS + JS puros, sem dependências externas pesadas.
"""

import argparse
import datetime
import html
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class WhatsAppHtmlGenerator:
    def __init__(
        self,
        input_txt: str = "dados_whatsapp/conversa_extraida/conversa_completa_processed.txt",
        output_html: Optional[str] = None,
        images_dir: str = "imagens_conversa",
        audios_dir: str = "audios_conversa",
        my_name: str = "Carlos Eduardo",
        contact_name: str = "Suelen Boff",
        title: Optional[str] = None,
    ):
        self.input_txt = Path(input_txt)
        if output_html:
            self.output_html = Path(output_html)
        else:
            self.output_html = self.input_txt.with_suffix(".html")
            
        self.images_dir = images_dir
        self.audios_dir = audios_dir
        self.my_name = my_name
        self.contact_name = contact_name
        self.title = title or f"Conversa WhatsApp — {contact_name} & {my_name}"

    def parse_messages(self) -> List[Dict]:
        """
        Lê e estrutura as mensagens do arquivo processed.txt.
        Retorna lista de mensagens agrupadas por data e remetente.
        """
        if not self.input_txt.exists():
            raise FileNotFoundError(f"Arquivo de conversa não encontrado: {self.input_txt}")

        msg_regex = re.compile(
            r"^(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}(?::\d{2})?)\s+-\s+([^:]+):\s*(.*)$"
        )
        img_desc_regex = re.compile(
            r"^🖼️\s*\[IMAGEM:\s*([^\]]+)\]\s*(?:Descrição:\s*)?(.*)$", re.IGNORECASE
        )
        audio_desc_regex = re.compile(
            r"^📝\s*\[ÁUDIO:\s*([^\]]+)\]\s*(?:Transcrição:\s*)?(.*)$", re.IGNORECASE
        )
        media_attach_regex = re.compile(
            r"([^\s]+\.(jpg|jpeg|png|webp|gif|opus|mp3|aac|ogg|wav|m4a|mp4))\s*\(arquivo anexado\)",
            re.IGNORECASE,
        )

        messages = []
        current_msg = None

        with open(self.input_txt, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.rstrip("\r\n")
                if not line.strip():
                    continue

                m = msg_regex.match(line)
                if m:
                    if current_msg:
                        messages.append(current_msg)
                    d_str, t_str, author, content = (
                        m.group(1),
                        m.group(2),
                        m.group(3).strip(),
                        m.group(4).strip(),
                    )
                    current_msg = {
                        "date": d_str,
                        "time": t_str,
                        "author": author,
                        "text_parts": [],
                        "images": [],
                        "audios": [],
                    }
                    if content:
                        self._process_content_line(
                            content, current_msg, media_attach_regex, img_desc_regex, audio_desc_regex
                        )
                elif current_msg:
                    self._process_content_line(
                        line, current_msg, media_attach_regex, img_desc_regex, audio_desc_regex
                    )

        if current_msg:
            messages.append(current_msg)

        return messages

    def _process_content_line(
        self, line: str, msg_dict: Dict, media_regex, img_regex, audio_regex
    ):
        img_m = img_regex.match(line)
        if img_m:
            fn = img_m.group(1).strip()
            desc = img_m.group(2).strip()
            # Se já foi registrado como anexo, atualiza a descrição
            found = False
            for img in msg_dict["images"]:
                if img["filename"] == fn:
                    img["description"] = desc
                    found = True
                    break
            if not found:
                msg_dict["images"].append({"filename": fn, "description": desc})
            return

        audio_m = audio_regex.match(line)
        if audio_m:
            fn = audio_m.group(1).strip()
            trans = audio_m.group(2).strip()
            found = False
            for aud in msg_dict["audios"]:
                if aud["filename"] == fn:
                    aud["transcription"] = trans
                    found = True
                    break
            if not found:
                msg_dict["audios"].append({"filename": fn, "transcription": trans})
            return

        att_m = media_regex.search(line)
        if att_m:
            fn = att_m.group(1).strip()
            ext = att_m.group(2).lower()
            if ext in ["jpg", "jpeg", "png", "webp", "gif"]:
                if not any(img["filename"] == fn for img in msg_dict["images"]):
                    msg_dict["images"].append({"filename": fn, "description": ""})
            elif ext in ["opus", "mp3", "aac", "ogg", "wav", "m4a"]:
                if not any(aud["filename"] == fn for aud in msg_dict["audios"]):
                    msg_dict["audios"].append({"filename": fn, "transcription": ""})
            else:
                msg_dict["text_parts"].append(line)
            return

        msg_dict["text_parts"].append(line)

    def generate_html(self) -> str:
        """
        Processa o arquivo TXT e grava o HTML final.
        """
        messages = self.parse_messages()
        total_msgs = len(messages)
        total_images = sum(len(m["images"]) for m in messages)
        total_audios = sum(len(m["audios"]) for m in messages)

        # Garantir diretório de saída
        self.output_html.parent.mkdir(parents=True, exist_ok=True)

        with open(self.output_html, "w", encoding="utf-8") as out:
            # Header e CSS
            out.write(self._get_html_head(total_msgs, total_images, total_audios))

            current_date = None

            for msg in messages:
                date_str = msg["date"]
                time_str = msg["time"]
                author = msg["author"]

                if date_str != current_date:
                    current_date = date_str
                    out.write(
                        f'<div class="date-divider"><span>📅 {html.escape(current_date)}</span></div>\n'
                    )

                is_me = (
                    self.my_name.lower() in author.lower()
                    or "carlos" in author.lower()
                )
                bubble_class = "msg-me" if is_me else "msg-other"
                sender_color = "#00a884" if is_me else "#9c27b0"

                out.write(f'<div class="msg-wrapper {bubble_class}">\n')
                out.write(f'  <div class="msg-bubble">\n')

                # Nome do autor (apenas na mensagem do contato para clareza)
                if not is_me:
                    out.write(
                        f'    <div class="msg-sender" style="color: {sender_color};">{html.escape(author)}</div>\n'
                    )

                # Imagens anexadas
                for img_info in msg["images"]:
                    fn = img_info["filename"]
                    desc = img_info["description"]
                    img_src = f"{self.images_dir}/{fn}".replace("\\", "/")
                    safe_desc = html.escape(desc, quote=True)
                    safe_fn = html.escape(fn, quote=True)

                    out.write('    <div class="media-container image-card">\n')
                    out.write(
                        f'      <img class="chat-thumb" src="{img_src}" alt="{safe_fn}" '
                        f'data-caption="{safe_desc}" loading="lazy" onclick="openLightbox(this)">\n'
                    )
                    if desc:
                        out.write(
                            f'      <div class="image-caption">🖼️ <span>{html.escape(desc)}</span></div>\n'
                        )
                    out.write('    </div>\n')

                # Áudios anexados
                for aud_info in msg["audios"]:
                    fn = aud_info["filename"]
                    trans = aud_info["transcription"]
                    aud_src = f"{self.audios_dir}/{fn}".replace("\\", "/")
                    safe_fn = html.escape(fn)
                    safe_trans = html.escape(trans)

                    out.write('    <div class="media-container audio-card">\n')
                    out.write('      <div class="audio-header">\n')
                    out.write(f'        <span class="audio-icon">🎤</span> <span class="audio-fn">{safe_fn}</span>\n')
                    out.write('      </div>\n')
                    out.write(f'      <audio controls preload="none" src="{aud_src}" class="audio-player"></audio>\n')
                    if trans:
                        out.write(
                            f'      <div class="audio-transcription">📝 <span>{safe_trans}</span></div>\n'
                        )
                    out.write('    </div>\n')

                # Textos
                if msg["text_parts"]:
                    text_html = "<br>".join(
                        html.escape(part) for part in msg["text_parts"]
                    )
                    out.write(f'    <div class="msg-text">{text_html}</div>\n')

                # Timestamp e status de envio
                ticks = '<span class="ticks">✓✓</span>' if is_me else ''
                out.write(
                    f'    <div class="msg-time">{html.escape(time_str)} {ticks}</div>\n'
                )

                out.write('  </div>\n')
                out.write('</div>\n')

            # Footer e Scripts
            out.write(self._get_html_foot())

        print(f"HTML gerado com sucesso: {self.output_html}")
        print(f"Total de mensagens: {total_msgs:,} | Imagens: {total_images:,} | Áudios: {total_audios:,}")
        return str(self.output_html)

    def _get_html_head(self, total_msgs: int, total_images: int, total_audios: int) -> str:
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(self.title)}</title>
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: #efeae2;
      background-image: radial-gradient(#d1cdc7 1px, transparent 1px);
      background-size: 20px 20px;
      color: #111b21;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}

    /* Header estilo WhatsApp Web */
    header.chat-header {{
      background-color: #008069;
      color: #ffffff;
      padding: 10px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
      z-index: 100;
      flex-shrink: 0;
    }}
    .header-left {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .avatar {{
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background-color: #dfe5e7;
      color: #008069;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      font-weight: bold;
    }}
    .header-info h1 {{
      font-size: 16px;
      font-weight: 600;
      line-height: 1.2;
    }}
    .header-info p {{
      font-size: 12px;
      opacity: 0.85;
    }}
    .header-stats {{
      font-size: 12px;
      background: rgba(0, 0, 0, 0.15);
      padding: 4px 10px;
      border-radius: 12px;
      white-space: nowrap;
    }}

    /* Container de mensagens */
    main.chat-container {{
      flex: 1;
      overflow-y: auto;
      padding: 16px 8%;
      display: flex;
      flex-direction: column;
      gap: 4px;
      scroll-behavior: smooth;
    }}

    @media (max-width: 768px) {{
      main.chat-container {{
        padding: 12px 3%;
      }}
    }}

    /* Divisor de data */
    .date-divider {{
      display: flex;
      justify-content: center;
      margin: 12px 0 8px 0;
    }}
    .date-divider span {{
      background-color: #ffffff;
      color: #54656f;
      font-size: 12px;
      font-weight: 500;
      padding: 5px 12px;
      border-radius: 8px;
      box-shadow: 0 1px 1px rgba(11, 20, 26, 0.12);
    }}

    /* Balões de Mensagem */
    .msg-wrapper {{
      display: flex;
      width: 100%;
      margin-bottom: 2px;
    }}
    .msg-wrapper.msg-me {{
      justify-content: flex-end;
    }}
    .msg-wrapper.msg-other {{
      justify-content: flex-start;
    }}

    .msg-bubble {{
      max-width: 65%;
      min-width: 120px;
      padding: 6px 9px 8px 9px;
      border-radius: 7.5px;
      position: relative;
      box-shadow: 0 1px 0.5px rgba(11, 20, 26, 0.13);
      font-size: 14.2px;
      line-height: 19px;
      word-wrap: break-word;
    }}

    @media (max-width: 600px) {{
      .msg-bubble {{
        max-width: 85%;
      }}
    }}

    .msg-me .msg-bubble {{
      background-color: #d9fdd3;
      border-top-right-radius: 0;
    }}
    .msg-other .msg-bubble {{
      background-color: #ffffff;
      border-top-left-radius: 0;
    }}

    .msg-sender {{
      font-size: 12.8px;
      font-weight: 600;
      margin-bottom: 3px;
    }}

    .msg-text {{
      color: #111b21;
      white-space: pre-wrap;
    }}

    .msg-time {{
      float: right;
      font-size: 11px;
      color: #667781;
      margin-left: 10px;
      margin-top: 4px;
      display: flex;
      align-items: center;
      gap: 3px;
    }}
    .ticks {{
      color: #53bdeb;
      font-size: 12px;
      font-weight: bold;
    }}

    /* Mídias */
    .media-container {{
      margin: 4px 0;
    }}

    /* Imagens */
    .image-card {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .chat-thumb {{
      max-width: 280px;
      max-height: 280px;
      width: auto;
      height: auto;
      border-radius: 6px;
      object-fit: cover;
      cursor: pointer;
      display: block;
      transition: transform 0.2s ease, filter 0.2s ease;
      background-color: #e9edef;
    }}
    .chat-thumb:hover {{
      filter: brightness(0.92);
      transform: scale(1.01);
    }}
    .image-caption {{
      font-size: 12.5px;
      line-height: 16px;
      color: #3b4a54;
      background: rgba(0, 0, 0, 0.04);
      padding: 6px 8px;
      border-radius: 5px;
      margin-top: 3px;
    }}

    /* Áudio */
    .audio-card {{
      background: rgba(0, 0, 0, 0.03);
      border-radius: 6px;
      padding: 6px 8px;
    }}
    .audio-header {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: #54656f;
      margin-bottom: 4px;
    }}
    .audio-player {{
      width: 100%;
      height: 32px;
      margin-bottom: 4px;
    }}
    .audio-transcription {{
      font-size: 12.5px;
      line-height: 16px;
      color: #065f46;
      background: #ecfdf5;
      border-left: 3px solid #10b981;
      padding: 4px 8px;
      border-radius: 0 4px 4px 0;
      margin-top: 4px;
    }}

    /* Lightbox Modal */
    .lightbox {{
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(11, 20, 26, 0.92);
      z-index: 1000;
      justify-content: center;
      align-items: center;
      flex-direction: column;
      padding: 20px;
    }}
    .lightbox.active {{
      display: flex;
    }}
    .lightbox-content {{
      max-width: 90vw;
      max-height: 80vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      position: relative;
    }}
    .lightbox-img {{
      max-width: 100%;
      max-height: 75vh;
      border-radius: 8px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
      object-fit: contain;
    }}
    .lightbox-caption {{
      color: #ffffff;
      font-size: 14px;
      margin-top: 12px;
      text-align: center;
      max-width: 800px;
      line-height: 1.4;
      background: rgba(0, 0, 0, 0.6);
      padding: 8px 16px;
      border-radius: 6px;
    }}
    .lightbox-close {{
      position: absolute;
      top: 15px;
      right: 25px;
      color: #ffffff;
      font-size: 32px;
      font-weight: bold;
      cursor: pointer;
      background: none;
      border: none;
      line-height: 1;
    }}
    .lightbox-close:hover {{
      color: #25d366;
    }}
  </style>
</head>
<body>
  <header class="chat-header">
    <div class="header-left">
      <div class="avatar">💬</div>
      <div class="header-info">
        <h1>{html.escape(self.contact_name)} &amp; {html.escape(self.my_name)}</h1>
        <p>Histórico Completo do WhatsApp</p>
      </div>
    </div>
    <div class="header-stats">
      {total_msgs:,} mensagens • {total_images:,} fotos • {total_audios:,} áudios
    </div>
  </header>

  <main class="chat-container">
"""

    def _get_html_foot(self) -> str:
        return """  </main>

  <div id="lightbox" class="lightbox" onclick="closeLightbox(event)">
    <button class="lightbox-close" onclick="closeLightbox(event)">&times;</button>
    <div class="lightbox-content" onclick="event.stopPropagation()">
      <img id="lightbox-img" class="lightbox-img" src="" alt="Imagem ampliada">
      <div id="lightbox-caption" class="lightbox-caption"></div>
    </div>
  </div>

  <script>
    function openLightbox(el) {
      const lb = document.getElementById('lightbox');
      const img = document.getElementById('lightbox-img');
      const cap = document.getElementById('lightbox-caption');
      img.src = el.src;
      const caption = el.getAttribute('data-caption') || '';
      cap.textContent = caption;
      cap.style.display = caption ? 'block' : 'none';
      lb.classList.add('active');
    }

    function closeLightbox(e) {
      const lb = document.getElementById('lightbox');
      lb.classList.remove('active');
      document.getElementById('lightbox-img').src = '';
    }

    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        closeLightbox();
      }
    });
  </script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(
        description="Gera uma interface HTML idêntica ao WhatsApp Web a partir de conversas processadas."
    )
    parser.add_argument(
        "--input",
        "-i",
        default="dados_whatsapp/conversa_extraida/conversa_completa_processed.txt",
        help="Caminho do arquivo TXT processado (padrão: dados_whatsapp/conversa_extraida/conversa_completa_processed.txt)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Caminho do arquivo HTML de saída (padrão: mesmo nome do TXT com extensão .html)",
    )
    parser.add_argument(
        "--images-dir",
        default="imagens_conversa",
        help="Diretório relativo das imagens em relação ao HTML (padrão: imagens_conversa)",
    )
    parser.add_argument(
        "--audios-dir",
        default="audios_conversa",
        help="Diretório relativo dos áudios em relação ao HTML (padrão: audios_conversa)",
    )
    parser.add_argument(
        "--my-name",
        default="Carlos Eduardo",
        help="Seu nome no chat para balões verdes à direita (padrão: Carlos Eduardo)",
    )
    parser.add_argument(
        "--contact-name",
        default="Suelen Boff",
        help="Nome do contato para balões brancos à esquerda (padrão: Suelen Boff)",
    )

    args = parser.parse_args()

    generator = WhatsAppHtmlGenerator(
        input_txt=args.input,
        output_html=args.output,
        images_dir=args.images_dir,
        audios_dir=args.audios_dir,
        my_name=args.my_name,
        contact_name=args.contact_name,
    )
    generator.generate_html()


if __name__ == "__main__":
    main()
