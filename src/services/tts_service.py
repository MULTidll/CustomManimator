from kokoro import KPipeline
import soundfile as sf
import os
from typing import Optional

class TTSService:
    def __init__(self, lang_code: str = 'a'):
        """Initialize the TTS service with Kokoro"""
        self.pipeline = KPipeline(lang_code=lang_code)
        self.voice_presets = {
            'en-us': 'af_heart',  # American English
            'en-uk': 'bf_heart',  # British English
            'es': 'es_heart',     # Spanish
            'fr': 'fr_heart',     # French
            'hi': 'hi_heart',     # Hindi
            'it': 'it_heart',     # Italian
            'pt-br': 'pt_heart',  # Brazilian Portuguese
            'ja': 'ja_heart',     # Japanese
            'zh': 'zh_heart',     # Mandarin Chinese
        }

    def generate(self, text: str, voice: str = 'en-us', output_path: Optional[str] = None) -> str:
        if not text:
            raise ValueError("Text cannot be empty")
            
        if voice not in self.voice_presets:
            raise ValueError(f"Unsupported voice: {voice}. Available voices: {list(self.voice_presets.keys())}")

        if output_path is None:
            output_path = f'output_{voice}.wav'
        
        generator = self.pipeline(text, voice=self.voice_presets[voice], speed=1, split_pattern=r'\n+')
        audio_data = []
        for _, _, audio in generator:
            audio_data.extend(audio)
        
        sf.write(output_path, audio_data, 24000)
        
        return output_path

def generate_audio(text: str, voice: str = 'en-us') -> str:
    """Generate audio from text using Kokoro TTS"""
    service = TTSService()
    return service.generate(text, voice)
