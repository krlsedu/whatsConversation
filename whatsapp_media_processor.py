#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WhatsApp Media Processor
Processes exported WhatsApp conversation ZIP files and replaces "<midia oculta>" 
with corresponding media file names and transcribes audio files using Gemini AI.
"""

import zipfile
import os
import re
import argparse
import json
import google.generativeai as genai
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set


class WhatsAppMediaProcessor:
    def __init__(self, zip_path: str, gemini_api_key: Optional[str] = None, enable_resume: bool = True):
        """
        Initialize the processor with a ZIP file path and optional Gemini API key.
        
        Args:
            zip_path (str): Path to the WhatsApp exported conversation ZIP file
            gemini_api_key (str, optional): Google Gemini API key for audio transcription
            enable_resume (bool): Enable resume functionality (default: True)
        """
        self.zip_path = Path(zip_path)
        self.media_files = []
        self.audio_files = []
        self.conversation_file = None
        self.gemini_api_key = gemini_api_key
        self.extract_dir = None
        self.checkpoint_file = None
        self.transcribed_files: Set[str] = set()
        self.enable_resume = enable_resume
        
        # Configure Gemini API if key is provided
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None
        
    def extract_and_analyze_zip(self) -> Tuple[str, List[str]]:
        """
        Extract ZIP file and identify conversation text file and media files.
        
        Returns:
            Tuple[str, List[str]]: Path to conversation file and list of media files
        """
        if not self.zip_path.exists():
            raise FileNotFoundError(f"ZIP file not found: {self.zip_path}")
            
        self.extract_dir = self.zip_path.parent / f"{self.zip_path.stem}_extracted"
        self.extract_dir.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.extract_dir)
            
        # Find conversation text file (usually .txt)
        txt_files = list(self.extract_dir.glob("*.txt"))
        if not txt_files:
            raise FileNotFoundError("No conversation text file found in ZIP")
        
        self.conversation_file = str(txt_files[0])
        
        # Define media extensions
        audio_extensions = {'.mp3', '.aac', '.ogg', '.opus'}
        other_media_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov', '.3gp', 
                                 '.pdf', '.doc', '.docx'}
        all_media_extensions = audio_extensions | other_media_extensions
        
        self.media_files = []
        self.audio_files = []
        
        for file_path in self.extract_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in all_media_extensions:
                if file_path.suffix.lower() in audio_extensions:
                    self.audio_files.append(file_path)
                else:
                    self.media_files.append(file_path.name)
                
        return self.conversation_file, self.media_files
    
    def _setup_checkpoint_file(self):
        """Setup checkpoint file path based on the ZIP file location."""
        if self.extract_dir:
            self.checkpoint_file = self.extract_dir / "transcription_checkpoint.json"
    
    def _load_checkpoint(self) -> Set[str]:
        """
        Load previously transcribed files from checkpoint file.
        
        Returns:
            Set[str]: Set of already transcribed audio filenames
        """
        if not self.checkpoint_file or not self.checkpoint_file.exists():
            return set()
        
        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get('transcribed_files', []))
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load checkpoint file: {e}")
            return set()
    
    def _save_checkpoint(self, transcribed_file: str):
        """
        Save progress to checkpoint file.
        
        Args:
            transcribed_file (str): Filename of the transcribed audio file
        """
        if not self.checkpoint_file:
            return
            
        self.transcribed_files.add(transcribed_file)
        
        try:
            checkpoint_data = {
                'transcribed_files': list(self.transcribed_files),
                'last_updated': str(Path().cwd() / 'timestamp')
            }
            
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Warning: Could not save checkpoint: {e}")
    
    def _clear_checkpoint(self):
        """Clear checkpoint file after successful completion."""
        if self.checkpoint_file and self.checkpoint_file.exists():
            try:
                self.checkpoint_file.unlink()
            except OSError as e:
                print(f"Warning: Could not delete checkpoint file: {e}")
    
    def transcribe_audio(self, audio_file_path: Path) -> str:
        """
        Transcribe an audio file using Gemini API.
        
        Args:
            audio_file_path (Path): Path to the audio file
            
        Returns:
            str: Transcription of the audio file or error message
        """
        if not self.model:
            return f"[ÁUDIO: {audio_file_path.name} - API não configurada]"
        
        try:
            # Upload the audio file to Gemini
            audio_file = genai.upload_file(str(audio_file_path))
            
            # Create prompt for Portuguese transcription
            prompt = """
            Por favor, transcreva este arquivo de áudio em português brasileiro. 
            Forneça apenas a transcrição do texto falado, sem comentários adicionais.
            Se não conseguir entender partes do áudio, indique com [inaudível].
            """
            
            # Generate transcription
            response = self.model.generate_content([prompt, audio_file])
            
            # Clean up the uploaded file
            genai.delete_file(audio_file.name)
            
            transcription = response.text.strip()
            if transcription:
                return f"[ÁUDIO: {audio_file_path.name}] Transcrição: {transcription}"
            else:
                return f"[ÁUDIO: {audio_file_path.name} - não foi possível transcrever]"
                
        except Exception as e:
            return f"[ÁUDIO: {audio_file_path.name} - erro: {str(e)}]"
    
    def process_conversation_file(self) -> str:
        """
        Process the conversation file and add transcriptions for audio files mentioned with "(arquivo anexado)".
        
        Returns:
            str: Path to the processed file
        """
        if not self.conversation_file or not os.path.exists(self.conversation_file):
            raise FileNotFoundError("Conversation file not found")
        
        # Setup checkpoint system
        self._setup_checkpoint_file()
        output_file = self.conversation_file.replace('.txt', '_processed.txt')
        resume_mode = False
        
        if not self.enable_resume:
            # Clear any existing checkpoint and processed file for fresh start
            print("Resume disabled. Starting fresh transcription...")
            self._clear_checkpoint()
            if os.path.exists(output_file):
                os.remove(output_file)
            self.transcribed_files = set()
        else:
            self.transcribed_files = self._load_checkpoint()
        
        # Check if we have a partially processed file to resume from
        if self.enable_resume and os.path.exists(output_file) and self.transcribed_files:
            print(f"Found existing processed file and checkpoint. Resuming from {len(self.transcribed_files)} already transcribed files...")
            resume_mode = True
            # Read the processed file instead of original
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            # Read the original conversation file
            with open(self.conversation_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
        # Pattern to find media files with "(arquivo anexado)"
        # Matches patterns like: "PTT-20250610-WA0041.opus (arquivo anexado)"
        media_pattern = r'([^\s]+\.(opus|mp3|aac|ogg|mp4|jpg|jpeg|png|gif|mov|3gp|pdf|doc|docx))\s*\(arquivo anexado\)'
        media_matches = list(re.finditer(media_pattern, content, re.IGNORECASE))
        
        if not media_matches:
            print("No media files with '(arquivo anexado)' found in the conversation file.")
            return self.conversation_file
            
        print(f"Found {len(media_matches)} media files with '(arquivo anexado)'")
        print(f"Found {len(self.audio_files)} audio files in ZIP")
        
        # Process content line by line to add transcriptions
        lines = content.split('\n')
        processed_lines = []
        audio_extensions = {'.opus', '.mp3', '.aac', '.ogg'}
        transcriptions_added = 0
        skipped_transcriptions = 0
        
        for line in lines:
            processed_lines.append(line)
            
            # Check if this line contains an audio file with "(arquivo anexado)"
            match = re.search(media_pattern, line, re.IGNORECASE)
            if match:
                filename = match.group(1)
                file_extension = Path(filename).suffix.lower()
                
                # If it's an audio file, add transcription
                if file_extension in audio_extensions:
                    # Clean filename by removing invisible characters
                    clean_filename = filename.replace('\u200e', '').replace('\u200f', '').strip()
                    
                    # Check if this file was already transcribed (resume mode)
                    if clean_filename in self.transcribed_files:
                        print(f"Skipping already transcribed audio: {filename}")
                        skipped_transcriptions += 1
                        continue
                    
                    # Find the corresponding audio file in the extracted files
                    audio_file_path = None
                    for audio_file in self.audio_files:
                        if audio_file.name == clean_filename:
                            audio_file_path = audio_file
                            break
                    
                    if audio_file_path and self.model:
                        print(f"Transcribing audio: {filename}...")
                        transcription = self.transcribe_audio(audio_file_path)
                        # Add transcription as a new line after the original line
                        processed_lines.append(f"📝 {transcription}")
                        transcriptions_added += 1
                        
                        # Save progress after each successful transcription
                        self._save_checkpoint(clean_filename)
                        
                        # Save intermediate results after each transcription
                        temp_content = '\n'.join(processed_lines)
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(temp_content)
                        
                    elif audio_file_path:
                        # Audio file found but no API key
                        processed_lines.append(f"📝 [ÁUDIO: {filename} - API não configurada]")
                        transcriptions_added += 1
                        # Save progress even without API key
                        self._save_checkpoint(clean_filename)
                        
                        # Save intermediate results
                        temp_content = '\n'.join(processed_lines)
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(temp_content)
                            
                    else:
                        # Audio file mentioned but not found in ZIP
                        processed_lines.append(f"📝 [ÁUDIO: {filename} - arquivo não encontrado no ZIP]")
                        transcriptions_added += 1
                        # Save progress even for missing files
                        self._save_checkpoint(clean_filename)
                        
                        # Save intermediate results
                        temp_content = '\n'.join(processed_lines)
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(temp_content)
        
        # Join processed lines back into content
        processed_content = '\n'.join(processed_lines)
        
        # Save final output file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(processed_content)
        
        # Clear checkpoint file after successful completion
        # Only clear if we processed everything successfully and there are no more files to process
        if transcriptions_added > 0 or skipped_transcriptions > 0:
            # Check if all audio files have been processed
            total_audio_files = len([match for match in re.finditer(r'([^\s]+\.(opus|mp3|aac|ogg))\s*\(arquivo anexado\)', content, re.IGNORECASE)])
            total_processed = len(self.transcribed_files)
            
            if total_processed >= total_audio_files:
                # All audio files processed, clear checkpoint
                print(f"All {total_audio_files} audio files processed. Clearing checkpoint.")
                self._clear_checkpoint()
            else:
                print(f"Progress saved: {total_processed}/{total_audio_files} audio files processed.")
            
        print(f"Processed file saved as: {output_file}")
        if resume_mode:
            print(f"Resume mode: Skipped {skipped_transcriptions} already transcribed files")
        print(f"New transcriptions added: {transcriptions_added}")
        return output_file
    
    def get_summary(self) -> Dict[str, int]:
        """
        Get summary of processing results.
        
        Returns:
            Dict[str, int]: Summary statistics
        """
        if not self.conversation_file:
            return {}
            
        with open(self.conversation_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Pattern to find media files with "(arquivo anexado)"
        media_pattern = r'([^\s]+\.(opus|mp3|aac|ogg|mp4|jpg|jpeg|png|gif|mov|3gp|pdf|doc|docx))\s*\(arquivo anexado\)'
        media_matches = len(re.findall(media_pattern, content, re.IGNORECASE))
        
        # Count audio files specifically
        audio_pattern = r'([^\s]+\.(opus|mp3|aac|ogg))\s*\(arquivo anexado\)'
        audio_matches = len(re.findall(audio_pattern, content, re.IGNORECASE))
        
        media_files_count = len(self.media_files)
        audio_files_count = len(self.audio_files)
        total_media_count = media_files_count + audio_files_count
        
        return {
            'media_entries_found': media_matches,
            'audio_entries_found': audio_matches,
            'media_files_found': media_files_count,
            'audio_files_found': audio_files_count,
            'total_media_files': total_media_count,
            'transcriptions_possible': min(audio_matches, audio_files_count)
        }


def main():
    """Main function to run the WhatsApp media processor."""
    parser = argparse.ArgumentParser(
        description='Process WhatsApp exported conversation ZIP files and replace "<midia oculta>" with media file names and transcribe audio files using Gemini AI.'
    )
    parser.add_argument('zip_file', help='Path to the WhatsApp conversation ZIP file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--gemini-api-key', help='Google Gemini API key for audio transcription')
    parser.add_argument('--resume', action='store_true', help='Resume from previous incomplete transcription (enabled by default)')
    parser.add_argument('--no-resume', action='store_true', help='Start fresh, ignoring any previous progress')
    
    args = parser.parse_args()
    
    # Check if API key is provided via environment variable if not in arguments
    gemini_api_key = args.gemini_api_key or os.getenv('GEMINI_API_KEY')
    
    if not gemini_api_key:
        print("Warning: No Gemini API key provided. Audio files will not be transcribed.")
        print("You can provide the API key using --gemini-api-key or set the GEMINI_API_KEY environment variable.")
    
    # Determine resume setting (default is True unless --no-resume is specified)
    enable_resume = not args.no_resume
    
    try:
        # Initialize processor
        processor = WhatsAppMediaProcessor(args.zip_file, gemini_api_key, enable_resume)
        
        if args.verbose:
            print(f"Processing ZIP file: {args.zip_file}")
        
        # Extract and analyze ZIP contents
        conversation_file, media_files = processor.extract_and_analyze_zip()
        
        if args.verbose:
            print(f"Conversation file: {conversation_file}")
            print(f"Audio files found: {len(processor.audio_files)}")
            for audio_file in processor.audio_files:
                print(f"  - {audio_file.name}")
            print(f"Other media files found: {len(media_files)}")
            for media_file in media_files:
                print(f"  - {media_file}")
        
        # Process the conversation file
        output_file = processor.process_conversation_file()
        
        # Show summary
        summary = processor.get_summary()
        print("\n=== SUMMARY ===")
        print(f"Media entries found in conversation: {summary.get('media_entries_found', 0)}")
        print(f"Audio entries found in conversation: {summary.get('audio_entries_found', 0)}")
        print(f"Audio files found in ZIP: {len(processor.audio_files)}")
        print(f"Other media files found in ZIP: {summary.get('media_files_found', 0)}")
        print(f"Transcriptions possible: {summary.get('transcriptions_possible', 0)}")
        print(f"Processed file: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())