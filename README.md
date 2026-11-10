# CscTrackerWhatsConversation — Extrator & Transcritor de Áudios do WhatsApp

Utilitário da stack **CscTracker** que processa bancos locais `msgstore.db` extraídos via ADB (**Método 2 — sem limite de anos/mensagens**) ou arquivos `.zip` exportados (**Método 1 — legado**), realizando a **transcrição automática de áudios** através do endpoint central **CscTracker AI** (`https://bff.csctracker.com/ai-processor/analyze`, seguindo o mesmo padrão do `CscTrackerVigilante` com `task="transcrição de audio do whats"`) e gerando a linha do tempo completa em `.txt` e `.pdf`.

## ✨ Funcionalidades Principais

- 🗄️ **Método 2 Integrado (ADB + SQLite `msgstore.db`)**: Extrai conversas de 8+ anos diretamente do banco descriptografado do WhatsApp (`msgstore.db.crypt15` -> `msgstore.db`) e das pastas `WhatsApp Voice Notes` / `WhatsApp Audio`, operando 100% no diretório corrente (`.\dados_whatsapp`)
- 🤖 **Integração Nativa com CscTracker AI (Padrão Vigilante)**: Chama `https://bff.csctracker.com/ai-processor/analyze` autenticado via `Bearer $TOKEN_CSCTRACKER`, enviando o áudio em Base64 com `task="transcrição de audio do whats"`
- ⏱️ **Linha do tempo com Hora, Minuto e Segundo (`DD/MM/YYYY HH:MM:SS`)**: Formata todas as mensagens com precisão de segundos (`Suelen Boff` vs `Carlos Eduardo`) e copia apenas os áudios da conversa para `.\dados_whatsapp\conversa_extraida\audios_conversa\`
- 📄 **Geração automática de PDF estruturado (`conversa_completa_processed.pdf`)**: Relatório visual agrupado por data, com cartões diferenciados por pessoa e destaque nas transcrições de áudio
- 🔄 **Checkpoint & Resume Inteligente**: Salva cada transcrição concluída em `transcription_checkpoint.json`, permitindo interromper e retomar exatamente de onde parou sem reprocessar áudios já transcritos

## 🚀 Como Executar (Passo a Passo)

### 1. Configurar o Token do CscTracker
No PowerShell, defina a variável de ambiente `TOKEN_CSCTRACKER` (a mesma usada no `CscTrackerVigilante`):
```powershell
$env:TOKEN_CSCTRACKER="seu_token_csctracker_aqui"
```

### 2. Executar o Script Automatizado via ADB (Método 2 — Recomendado)
1. Com o celular conectado via USB e Depuração USB ativa, abra o PowerShell na pasta do projeto e rode:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\exportar_whatsapp_adb.ps1
```
*(Ou passando parâmetros diretamente: `.\exportar_whatsapp_adb.ps1 -Chave64Digitos "SUA_CHAVE_64_HEX" -TelefoneContato "99999999" -TokenCscTracker "SEU_TOKEN"`).*

### 3. Ou Executar Diretamente via Python
```powershell
python whatsapp_media_processor.py --db ".\dados_whatsapp\msgstore.db" --media-dir ".\dados_whatsapp\raw_android" --phone "99999999" --contact-name "Suelen Boff" --my-name "Carlos Eduardo" --pdf --verbose
```

## 🔧 Opções da Linha de Comando

| Opção | Descrição |
|-------|-----------|
| `--db` | Caminho para o banco SQLite `msgstore.db` descriptografado (Método 2) |
| `--media-dir` | Pasta raiz contendo `WhatsApp Voice Notes` e `WhatsApp Audio` extraídos via ADB |
| `--phone` | Dígitos do telefone ou nome para localizar a conversa no `msgstore.db` |
| `--contact-name` | Nome de exibição do contato (padrão: `Suelen Boff`) |
| `--my-name` | Seu nome de exibição (padrão: `Carlos Eduardo`) |
| `--work-dir` | Diretório de trabalho (padrão: `./dados_whatsapp` no diretório corrente) |
| `--token-csctracker` | Token Bearer do CscTracker AI (ou via env `TOKEN_CSCTRACKER`) |
| `--gemini-model` | Modelo no CscTracker AI (`flash`, `pro`, `lite` — padrão: `flash`) |
| `--thinking-level` | Nível de raciocínio (`low` ou `minimal` — padrão: `low`) |
| `--pdf` / `--no-pdf` | Ativa (padrão) ou desativa a geração do PDF estruturado ao final |
| `--resume` / `--no-resume` | Retoma do checkpoint (padrão) ou reinicia do zero |
