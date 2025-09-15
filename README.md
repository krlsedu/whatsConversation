# WhatsApp Media Processor com Transcrição de Áudio

Uma aplicação Python avançada que processa arquivos ZIP de conversas exportadas do WhatsApp e **transcreve arquivos de áudio automaticamente** usando Google Gemini AI em português brasileiro. A aplicação detecta arquivos de mídia mencionados no formato "(arquivo anexado)" e adiciona transcrições completas para áudios.

## ✨ Funcionalidades Principais

- 📁 **Extração automática** de arquivos ZIP de conversas do WhatsApp
- 🔍 **Identificação inteligente** de arquivos de texto da conversa e mídia
- 🎵 **TRANSCRIÇÃO AUTOMÁTICA DE ÁUDIOS** usando Google Gemini AI em português brasileiro
- 🔄 **FUNCIONALIDADE DE RESUMO** - Continue de onde parou se o processamento for interrompido
- 📝 **Processamento de mídia com "(arquivo anexado)"**:
  - **Transcrições completas** para arquivos de áudio (.opus, .mp3, .aac, .ogg)
  - **Detecção automática** de outros tipos de mídia (imagens, vídeos, documentos)
- 💾 **Salvamento automático de progresso** durante o processamento
- 📊 **Estatísticas detalhadas** do processamento
- 🛡️ **Tratamento robusto de erros** e recuperação automática

## 📋 Requisitos do Sistema

- **Python 3.6 ou superior**
- **Chave da API do Google Gemini** (obrigatória para transcrição de áudio)
- Conexão com a internet (para chamadas da API Gemini)
- Bibliotecas Python:
  - `google-generativeai` (instalação automática)
  - Bibliotecas padrão: `zipfile`, `os`, `re`, `argparse`, `pathlib`, `typing`, `json`

## 🚀 Instalação

### Método 1: Instalação Completa

```bash
# Clone o repositório
git clone <repository-url>
cd whatsConversation

# Instale as dependências
pip install google-generativeai

# Execute o processador
python whatsapp_media_processor.py seu_arquivo.zip
```

### Método 2: Download Direto

1. Baixe o arquivo `whatsapp_media_processor.py`
2. Instale as dependências: `pip install google-generativeai`
3. Execute: `python whatsapp_media_processor.py seu_arquivo.zip`

## 🔑 Configuração da API Gemini

### Obter Chave da API

1. Acesse [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Faça login com sua conta Google
3. Clique em "Create API Key"
4. Copie a chave gerada

### Configurar a Chave

**Opção 1: Variável de Ambiente (Recomendada)**
```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY="sua_chave_aqui"

# Windows (CMD)
set GEMINI_API_KEY=sua_chave_aqui

# Linux/Mac
export GEMINI_API_KEY="sua_chave_aqui"
```

**Opção 2: Parâmetro da Linha de Comando**
```bash
python whatsapp_media_processor.py arquivo.zip --gemini-api-key="sua_chave_aqui"
```

## 💻 Como Usar

### Sintaxe Básica

```bash
python whatsapp_media_processor.py <caminho_para_arquivo_zip> [opções]
```

### 🔧 Opções da Linha de Comando

| Opção | Descrição |
|-------|-----------|
| `--verbose`, `-v` | Ativa saída detalhada do processamento |
| `--gemini-api-key` | Especifica a chave da API do Google Gemini |
| `--resume` | Continua de onde parou (padrão habilitado) |
| `--no-resume` | Força início do zero, ignora progresso anterior |

### 📝 Exemplos Práticos

#### Uso Básico (Recomendado)
```bash
# Com variável de ambiente configurada
python whatsapp_media_processor.py "Conversa do WhatsApp.zip"
```

#### Processamento com API Key Inline
```bash
python whatsapp_media_processor.py "conversa.zip" --gemini-api-key="sua_chave_gemini_aqui"
```

#### Processamento Detalhado
```bash
# Ver progresso detalhado durante execução
python whatsapp_media_processor.py "conversa.zip" --verbose
```

#### Controle de Resumo
```bash
# Forçar início do zero (apagar progresso anterior)
python whatsapp_media_processor.py "conversa.zip" --no-resume

# Continuar processamento interrompido (comportamento padrão)
python whatsapp_media_processor.py "conversa.zip" --resume --verbose
```

#### Exemplo Completo (Windows)
```powershell
# Configurar API key
$env:GEMINI_API_KEY="sua_chave_aqui"

# Processar com saída detalhada
python whatsapp_media_processor.py "C:\Downloads\Conversa do WhatsApp com João.zip" --verbose
```

## 🔄 Sistema de Resumo Inteligente

O WhatsApp Media Processor possui um **sistema de checkpoint automático** que salva o progresso continuamente, permitindo retomar o processamento exatamente de onde parou em caso de interrupção.

### 🛠️ Como Funciona

| Etapa | Descrição |
|-------|-----------|
| 1️⃣ **Salvamento Automático** | Progresso salvo após cada transcrição em `transcription_checkpoint.json` |
| 2️⃣ **Detecção Inteligente** | Ao reiniciar, detecta automaticamente processamentos incompletos |
| 3️⃣ **Continuação Otimizada** | Pula arquivos já transcritos e processa apenas os pendentes |
| 4️⃣ **Limpeza Automática** | Remove checkpoint quando todas as transcrições estão concluídas |

### 📱 Cenários Práticos de Uso

#### ⚠️ Quando o Resume é Útil
- **Erro de API**: Falhas na API do Gemini durante processamento
- **Interrupção Manual**: Parar o programa com `Ctrl+C` 
- **Problemas de Conexão**: Internet instável durante transcrições
- **Conversas Grandes**: Milhares de áudios processados em etapas
- **Limite de API**: Atingir quotas da API Gemini

#### 💡 Exemplo de Fluxo de Trabalho
```bash
# 1. Iniciar processamento
python whatsapp_media_processor.py "conversa_grande.zip" --verbose

# Saída esperada:
# Transcribing audio: PTT-001.opus...
# Transcribing audio: PTT-002.opus...
# [INTERRUPÇÃO MANUAL - Ctrl+C]

# 2. Retomar processamento 
python whatsapp_media_processor.py "conversa_grande.zip" --verbose

# Saída esperada:
# Found existing processed file and checkpoint. Resuming from 2 already transcribed files...
# Skipping already transcribed audio: PTT-001.opus
# Skipping already transcribed audio: PTT-002.opus
# Transcribing audio: PTT-003.opus...
```

### 🎛️ Controle Manual do Resume

```bash
# ✅ Padrão - resume automático habilitado
python whatsapp_media_processor.py conversa.zip

# 🆕 Forçar início do zero (apagar todo progresso anterior)
python whatsapp_media_processor.py conversa.zip --no-resume

# ✨ Explicitamente habilitar resume (redundante mas claro)
python whatsapp_media_processor.py conversa.zip --resume --verbose
```

## ⚙️ Como Funciona Internamente

| Etapa | Descrição | Detalhes |
|-------|-----------|----------|
| 1️⃣ | **Extração** | Descompacta o ZIP em pasta temporária com nome `_extracted` |
| 2️⃣ | **Identificação** | Localiza arquivo `.txt` da conversa e classifica arquivos de mídia |
| 3️⃣ | **Verificação de Resume** | Carrega checkpoint se existir, detecta progresso anterior |
| 4️⃣ | **Processamento** | Busca padrão `(arquivo anexado)` no texto da conversa |
| 5️⃣ | **Transcrição** | Processa áudios com Gemini AI, salva progresso continuamente |
| 6️⃣ | **Saída** | Gera `_processed.txt` com transcrições inseridas |

## 📁 Formatos de Mídia Suportados

| Categoria | Extensões | Processamento |
|-----------|-----------|---------------|
| 🎵 **Áudio** | `.opus`, `.mp3`, `.aac`, `.ogg` | **Transcrição automática** |
| 🖼️ **Imagens** | `.jpg`, `.jpeg`, `.png`, `.gif` | Detecção de presença |
| 🎥 **Vídeos** | `.mp4`, `.mov`, `.3gp` | Detecção de presença |
| 📄 **Documentos** | `.pdf`, `.doc`, `.docx` | Detecção de presença |

## 📝 Formato do Arquivo de Saída

### Exemplo de Entrada (conversa original):
```
10/06/2025 17:35 - Carlos Eduardo: ‎PTT-20250610-WA0041.opus (arquivo anexado)
10/06/2025 17:40 - Maria: ‎IMG-20250610-WA0042.jpg (arquivo anexado)
```

### Exemplo de Saída (conversa processada):
```
10/06/2025 17:35 - Carlos Eduardo: ‎PTT-20250610-WA0041.opus (arquivo anexado)
📝 [ÁUDIO: PTT-20250610-WA0041.opus] Transcrição: Oi Maria, tudo bem? Vou chegar um pouco mais tarde hoje.

10/06/2025 17:40 - Maria: ‎IMG-20250610-WA0042.jpg (arquivo anexado)
```

### Possíveis Estados de Transcrição:
```
📝 [ÁUDIO: arquivo.opus] Transcrição: [conteúdo transcrito]
📝 [ÁUDIO: arquivo.opus - API não configurada]
📝 [ÁUDIO: arquivo.opus - arquivo não encontrado no ZIP]
📝 [ÁUDIO: arquivo.opus - erro: detalhes do erro]
```

## Exemplo de Uso Programático

```python
from whatsapp_media_processor import WhatsAppMediaProcessor

# Inicializar o processador
processor = WhatsAppMediaProcessor('conversa.zip')

# Extrair e analisar o ZIP
conversation_file, media_files = processor.extract_and_analyze_zip()

# Processar o arquivo de conversa
output_file = processor.process_conversation_file()

# Obter estatísticas
summary = processor.get_summary()
print(f"Substituições realizadas: {summary['replacements_made']}")
```

## 📊 Exemplo de Saída do Programa

### Processamento Bem-sucedido
```
Processing ZIP file: Conversa do WhatsApp com João.zip
Conversation file: ...\Conversa do WhatsApp com João_extracted\conversa.txt
Audio files found: 3
  - PTT-20250610-WA0041.opus
  - PTT-20250610-WA0042.opus  
  - PTT-20250610-WA0043.opus
Other media files found: 2
  - IMG-20250610-WA0044.jpg
  - VID-20250610-WA0045.mp4

Found 5 media files with '(arquivo anexado)'
Found 3 audio files in ZIP
Transcribing audio: PTT-20250610-WA0041.opus...
Transcribing audio: PTT-20250610-WA0042.opus...
Transcribing audio: PTT-20250610-WA0043.opus...
Processed file saved as: ...\conversa_processed.txt
New transcriptions added: 3

=== SUMMARY ===
Media entries found in conversation: 5
Audio entries found in conversation: 3
Audio files found in ZIP: 3
Other media files found in ZIP: 2
Transcriptions possible: 3
Processed file: ...\Conversa do WhatsApp com João_extracted\conversa_processed.txt
```

### Processamento com Resume
```
Found existing processed file and checkpoint. Resuming from 1 already transcribed files...
Skipping already transcribed audio: PTT-20250610-WA0041.opus
Transcribing audio: PTT-20250610-WA0042.opus...
Progress saved: 2/3 audio files processed.
```

## 🔧 Solução de Problemas

### ❌ Erros Comuns e Soluções

| Erro | Causa Possível | Solução |
|------|----------------|---------|
| `FileNotFoundError: ZIP file not found` | Caminho incorreto do arquivo | Verificar se o caminho está correto e usar aspas |
| `No conversation text file found in ZIP` | ZIP não contém arquivo .txt | Verificar se exportou conversa corretamente do WhatsApp |
| `Warning: No Gemini API key provided` | API key não configurada | Configurar `GEMINI_API_KEY` ou usar `--gemini-api-key` |
| `Error: [API Error details]` | Problema com API Gemini | Verificar quota da API, conexão com internet |
| `UnicodeDecodeError` | Problemas de codificação | Arquivo pode estar corrompido, reexportar do WhatsApp |

### 🛠️ Troubleshooting Detalhado

#### Problema: "python não é reconhecido"
```bash
# Soluções:
python3 whatsapp_media_processor.py arquivo.zip
py whatsapp_media_processor.py arquivo.zip
# Ou instalar Python e adicionar ao PATH
```

#### Problema: Transcrições com "[inaudível]"
- **Causa**: Áudio de baixa qualidade ou muito ruído
- **Solução**: Normal, indica que a IA não conseguiu identificar partes do áudio

#### Problema: Processamento muito lento
- **Causa**: Muitos arquivos de áudio
- **Solução**: Use `--verbose` para acompanhar progresso, ou processe em etapas

#### Problema: Quota da API Gemini esgotada
- **Causa**: Limite diário/mensal atingido
- **Solução**: Aguardar reset da quota ou usar `--resume` para continuar depois

### 📝 Logs e Depuração

Para mais informações durante a execução:
```bash
# Ativar modo verbose
python whatsapp_media_processor.py arquivo.zip --verbose

# Ver arquivos gerados
ls -la *_extracted/  # Linux/Mac
dir *_extracted\     # Windows
```

## 📌 Notas Importantes

- ✅ **Segurança**: Arquivo original nunca é modificado
- 🔤 **Codificação**: UTF-8 usado para compatibilidade internacional  
- 📁 **Organização**: Arquivos extraídos ficam em pasta `_extracted`
- 🔄 **Resume**: Checkpoint salvo automaticamente após cada transcrição
- 🌐 **Conectividade**: Requer internet apenas para transcrições (API Gemini)

## Licença

Este projeto é de código aberto e pode ser usado livremente.