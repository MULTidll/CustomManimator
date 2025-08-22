from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import tempfile
import os
import subprocess
import logging
import shutil
import traceback
from src.api.gemini import generate_video
from src.api.fallback_gemini import fix_manim_code
from src.services.manim_service import create_manim_video
from src.services.tts_service import generate_audio

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()

class TextIdeaRequest(BaseModel):
    idea: str

class FixCodeRequest(BaseModel):
    faulty_code: str
    error_message: str
    original_context: str

@app.post("/generate_video/text")
async def generate_from_text(request: TextIdeaRequest):
    files_to_cleanup = set()
    try:
        video_data, script = generate_video(idea=request.idea)
        if not video_data or not script:
            raise HTTPException(status_code=500, detail="Failed to generate initial script/code.")
        try:
            audio_file, subtitle_file = generate_audio(script)
            if audio_file:
                files_to_cleanup.add(audio_file)
            if subtitle_file:
                files_to_cleanup.add(subtitle_file)
        except ValueError as e:
            audio_file, subtitle_file = None, None
        current_manim_code = video_data["manim_code"]
        current_script = script
        current_audio_file = audio_file
        current_subtitle_file = subtitle_file
        max_retries = 2
        final_video = None
        for attempt in range(max_retries + 1):
            try:
                final_video = create_manim_video(
                    video_data,
                    current_manim_code,
                    audio_file=current_audio_file,
                    subtitle_file=current_subtitle_file,
                )
                break
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                error_output = e.stderr.decode('utf-8', errors='ignore') if hasattr(e, "stderr") and e.stderr else str(e)
                if attempt < max_retries:
                    fixed_video_data, fixed_script = fix_manim_code(
                        faulty_code=current_manim_code,
                        error_message=error_output,
                        original_context=request.idea,
                    )
                    if fixed_video_data and fixed_script is not None:
                        current_manim_code = fixed_video_data["manim_code"]
                        if fixed_script != current_script and fixed_script:
                            current_script = fixed_script
                            try:
                                new_audio, new_subtitle = generate_audio(current_script)
                                if new_audio: files_to_cleanup.add(new_audio)
                                if new_subtitle: files_to_cleanup.add(new_subtitle)
                                current_audio_file = new_audio
                                current_subtitle_file = new_subtitle
                            except ValueError:
                                current_audio_file, current_subtitle_file = None, None
                    else:
                        final_video = None
                        break
                else:
                    final_video = None
        if final_video and os.path.exists(final_video):
            return {
                "video_file": final_video,
                "narration": current_script,
                "subtitle_file": current_subtitle_file,
                "error": None
            }
        else:
            raise HTTPException(status_code=500, detail="Could not generate the video after multiple attempts.")
    except Exception as e:
        tb_str = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}\n{tb_str}")
    finally:
        for f_path in files_to_cleanup:
            if f_path and os.path.exists(f_path):
                try:
                    os.remove(f_path)
                except OSError:
                    pass

@app.post("/generate_video/pdf")
async def generate_from_pdf(file: UploadFile = File(...)):
    files_to_cleanup = set()
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            shutil.copyfileobj(file.file, temp_pdf)
            pdf_path = temp_pdf.name
            files_to_cleanup.add(pdf_path)
        video_data, script = generate_video(pdf_path=pdf_path)
        if not video_data or not script:
            raise HTTPException(status_code=500, detail="Failed to generate initial script/code.")
        try:
            audio_file, subtitle_file = generate_audio(script)
            if audio_file:
                files_to_cleanup.add(audio_file)
            if subtitle_file:
                files_to_cleanup.add(subtitle_file)
        except ValueError:
            audio_file, subtitle_file = None, None
        current_manim_code = video_data["manim_code"]
        current_script = script
        current_audio_file = audio_file
        current_subtitle_file = subtitle_file
        max_retries = 2
        final_video = None
        for attempt in range(max_retries + 1):
            try:
                final_video = create_manim_video(
                    video_data,
                    current_manim_code,
                    audio_file=current_audio_file,
                    subtitle_file=current_subtitle_file,
                )
                break
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                error_output = e.stderr.decode('utf-8', errors='ignore') if hasattr(e, "stderr") and e.stderr else str(e)
                if attempt < max_retries:
                    fixed_video_data, fixed_script = fix_manim_code(
                        faulty_code=current_manim_code,
                        error_message=error_output,
                        original_context=f"Summary/concept from PDF: {file.filename}",
                    )
                    if fixed_video_data and fixed_script is not None:
                        current_manim_code = fixed_video_data["manim_code"]
                        if fixed_script != current_script and fixed_script:
                            current_script = fixed_script
                            try:
                                new_audio, new_subtitle = generate_audio(current_script)
                                if new_audio: files_to_cleanup.add(new_audio)
                                if new_subtitle: files_to_cleanup.add(new_subtitle)
                                current_audio_file = new_audio
                                current_subtitle_file = new_subtitle
                            except ValueError:
                                current_audio_file, current_subtitle_file = None, None
                    else:
                        final_video = None
                        break
                else:
                    final_video = None
        if final_video and os.path.exists(final_video):
            return {
                "video_file": final_video,
                "narration": current_script,
                "subtitle_file": current_subtitle_file,
                "error": None
            }
        else:
            raise HTTPException(status_code=500, detail="Could not generate the video after multiple attempts.")
    except Exception as e:
        tb_str = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}\n{tb_str}")
    finally:
        for f_path in files_to_cleanup:
            if f_path and os.path.exists(f_path):
                try:
                    os.remove(f_path)
                except OSError:
                    pass

@app.post("/fix_code")
async def fix_code(request: FixCodeRequest):
    try:
        fixed_video_data, fixed_script = fix_manim_code(
            faulty_code=request.faulty_code,
            error_message=request.error_message,
            original_context=request.original_context
        )
        if not fixed_video_data:
            raise HTTPException(status_code=500, detail="Failed to fix code.")
        return {
            "fixed_code": fixed_video_data["manim_code"],
            "narration": fixed_script,
            "error": None
        }
    except Exception as e:
        tb_str = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}\n{tb_str}")
