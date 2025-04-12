import streamlit as st
import os
import tempfile
import subprocess
import logging

from api.gemini import generate_video
from api.fallback_gemini import fix_manim_code
from services.manim_service import create_manim_video
from services.tts_service import generate_audio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    st.title("Manimator")
    st.write("Generate videos from text ideas or PDF files, You can also just paste arxiv links ;p")
    input_type = st.radio("Choose input type:", ("Text Idea", "Upload PDF"))

    idea = None
    uploaded_file = None
    pdf_path = None
    original_context = ""
    audio_file = None
    current_audio_file = None
    if input_type == "Text Idea":
        idea = st.text_area("Enter your idea:")
        if idea:
            original_context = idea
    else:
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
        if uploaded_file:
            original_context = f"Summary/concept from PDF: {uploaded_file.name}"

    if st.button("Generate Video"):
        temp_pdf_file = None
        video_data = None
        script = None
        audio_file = None
        final_video = None
        max_retries = 1

        try:
            if input_type == "Text Idea" and idea:
                with st.spinner("Generating initial script and code from idea..."):
                    logging.info(f"Generating video from idea: {idea[:50]}...")
                    video_data, script = generate_video(idea=idea)
            elif input_type == "Upload PDF" and uploaded_file is not None:
                with st.spinner("Generating initial script and code from PDF..."):
                    logging.info(f"Generating video from PDF: {uploaded_file.name}")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                        temp_pdf.write(uploaded_file.getvalue())
                        pdf_path = temp_pdf.name
                        temp_pdf_file = pdf_path
                    video_data, script = generate_video(pdf_path=pdf_path)
            else:
                st.error("Please provide an idea or upload a PDF.")
                return

            if not video_data or not script:
                 st.error("Failed to generate initial script/code from Gemini.")
                 return

            with st.spinner("Generating audio..."):
                 logging.info("Generating audio for the script.")
                 try:
                     audio_file = generate_audio(script)
                 except ValueError as e:
                     st.warning(f"Could not generate audio: {e}. Proceeding without audio.")
                     audio_file = None

            current_manim_code = video_data["manim_code"]
            current_script = script
            current_audio_file = audio_file

            for attempt in range(max_retries + 1):
                try:
                    with st.spinner(f"Attempt {attempt + 1}: Creating Manim video..."):
                        logging.info(f"Attempt {attempt + 1} to create Manim video.")
                        final_video = create_manim_video(
                            {"manim_code": current_manim_code, "output_file": "output.mp4"},
                            current_manim_code,
                            audio_file=current_audio_file
                        )
                    logging.info("Manim video creation successful.")
                    break
                except subprocess.CalledProcessError as e:
                    logging.error(f"Manim execution failed on attempt {attempt + 1}.")
                    st.warning(f"Attempt {attempt + 1} failed. Manim error:\n```\n{e.stderr.decode() if e.stderr else 'No stderr captured.'}\n```")
                    if attempt < max_retries:
                        st.info("Attempting to fix the code using fallback...")
                        logging.info("Calling fallback Gemini to fix code.")
                        error_message = e.stderr.decode() if e.stderr else "Manim execution failed without specific error output."

                        fixed_video_data, fixed_script = fix_manim_code(
                            faulty_code=current_manim_code,
                            error_message=error_message,
                            original_context=original_context
                        )

                        if fixed_video_data and fixed_script is not None:
                            st.success("Fallback successful! Retrying video generation with fixed code.")
                            logging.info("Fallback successful. Received fixed code.")
                            current_manim_code = fixed_video_data["manim_code"]
                            if fixed_script != current_script and fixed_script:
                                st.info("Narration script was updated by the fallback. Regenerating audio...")
                                logging.info("Regenerating audio for updated script.")
                                current_script = fixed_script
                                try:
                                     current_audio_file = generate_audio(current_script)
                                except ValueError as e:
                                     st.warning(f"Could not generate audio for fixed script: {e}. Proceeding without audio.")
                                     current_audio_file = None
                            elif not fixed_script:
                                 st.warning("Fallback provided code but no narration. Using original audio (if any).")
                                 logging.warning("Fallback provided empty narration.")
                                 current_script = ""
                                 current_audio_file = None
                            else:
                                logging.info("Fallback kept the original narration.")
                        else:
                            st.error("Fallback failed to fix the code. Stopping.")
                            logging.error("Fallback failed to return valid code/script.")
                            final_video = None
                            break
                    else:
                        st.error(f"Manim failed after {max_retries + 1} attempts. Could not generate video.")
                        logging.error(f"Manim failed after {max_retries + 1} attempts.")
                        final_video = None
                except Exception as e:
                    st.error(f"An unexpected error occurred during video creation: {str(e)}")
                    logging.exception("Unexpected error during create_manim_video call.")
                    final_video = None
                    break

            if final_video and os.path.exists(final_video):
                st.success("Video generated successfully!")
                st.video(final_video)
                st.write("Generated Narration:")
                st.text_area("Narration", current_script if current_script is not None else "Narration could not be generated.", height=150)
            elif not final_video:
                 pass
            else:
                st.error("Error: Generated video file not found after processing.")
                logging.error(f"Final video file '{final_video}' not found.")

        except FileNotFoundError as e:
             st.error(f"Error: A required file was not found. {str(e)}")
             logging.exception("FileNotFoundError during generation process.")
        except ValueError as e:
             st.error(f"Input Error: {str(e)}")
             logging.exception("ValueError during generation process.")
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
            logging.exception("Unhandled exception in main generation block.")
        finally:
            if temp_pdf_file and os.path.exists(temp_pdf_file):
                try:
                    os.remove(temp_pdf_file)
                    logging.info(f"Removed temporary file: {temp_pdf_file}")
                except OSError as e:
                    logging.error(f"Error removing temporary file {temp_pdf_file}: {e}")
            if audio_file and os.path.exists(audio_file) and audio_file != current_audio_file:
                 try:
                     os.remove(audio_file)
                     logging.info(f"Removed temporary audio file: {audio_file}")
                 except OSError as e:
                     logging.error(f"Error removing temporary audio file {audio_file}: {e}")
            if current_audio_file and os.path.exists(current_audio_file):
                 try:
                     os.remove(current_audio_file)
                     logging.info(f"Removed potentially updated temporary audio file: {current_audio_file}")
                 except OSError as e:
                     logging.error(f"Error removing potentially updated temporary audio file {current_audio_file}: {e}")
    st.markdown("<br><br>", unsafe_allow_html=True) 
    st.markdown("---")
    
    
    st.markdown("""
        ### Want to help improve this app?
        - Give good Manim Examples and make PRs in guide.md, find it in repo [GitHub](https://github.com/mostlykiguess/Manimator)
        - Report issues on [GitHub Issues](https://github.com/mostlykiguess/Manimator/issues)
        - Email problematic prompts to me 
        """)
    

if __name__ == "__main__":
    main()
