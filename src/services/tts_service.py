from kokoro import KPipeline
import soundfile as sf
import os
import numpy as np
from typing import Optional, Tuple, List, Dict
from .subtitle_service import generate_subtitle_file


def generate_audio(
    text: str, voice_lang: str = "a", output_filename: str = "output_audio.wav"
) -> Tuple[Optional[str], Optional[str]]:
    """
    Generate audio from text using Kokoro TTS and create a synchronized subtitle file.

    Args:
        text (str): The text to synthesize.
        voice_lang (str): The language code for the voice (e.g., 'a' for American English).
        output_filename (str): The desired output filename for the audio.

    Returns:
        A tuple containing the path to the audio file and the subtitle file, or (None, None) on failure.
    """
    if not text.strip():
        raise ValueError("Text for TTS cannot be empty.")

    try:
        pipeline = KPipeline(lang_code=voice_lang)
        voice_preset = "af_heart"

        audio_segments = []
        all_tokens: List[Dict] = []
        current_time_offset = 0.0
        rate = 24000

        for result in pipeline(
            text, voice=voice_preset, speed=1.0, split_pattern=r"\n+"
        ):
            audio_segments.append(result.audio)

            chunk_duration = len(result.audio) / rate

            if hasattr(result, "tokens"):
                for token in result.tokens:
                    start_ts = token.start_ts if token.start_ts is not None else 0
                    end_ts = (
                        token.end_ts if token.end_ts is not None else chunk_duration
                    )

                    all_tokens.append(
                        {
                            "text": token.text.strip(),
                            "start": current_time_offset + start_ts,
                            "end": current_time_offset + end_ts,
                        }
                    )

            current_time_offset += chunk_duration

        if not audio_segments:
            return None, None

        final_audio = np.concatenate(audio_segments)
        sf.write(output_filename, final_audio, rate)

        subtitle_file_path = generate_subtitle_file(all_tokens, output_filename)

        return output_filename, subtitle_file_path

    except Exception as e:
        logging.error(
            f"An error occurred during TTS or subtitle generation: {e}", exc_info=True
        )
        if os.path.exists(output_filename):
            os.remove(output_filename)
        return None, None
