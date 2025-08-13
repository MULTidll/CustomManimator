import streamlit as st
import os
import tempfile
import subprocess
import logging

from api.gemini import generate_video
from api.fallback_gemini import fix_manim_code
from services.manim_service import create_manim_video
from services.tts_service import generate_audio

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def main():
    st.title("Manimator")
    st.write(
        "Generate videos from text ideas or PDF files, You can also just paste arxiv links ;p"
    )
    input_type = st.radio("Choose input type:", ("Text Idea", "Upload PDF"))

    idea = None
    uploaded_file = None
    original_context = ""

    if input_type == "Text Idea":
        idea = st.text_area("Enter your idea:")
        if idea:
            original_context = idea
    else:
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
        if uploaded_file:
            original_context = f"Summary/concept from PDF: {uploaded_file.name}"

    if st.button("Generate Video"):
        files_to_cleanup = set()
        video_data = None
        script = None
        final_video = None
        max_retries = 2  # retries for fallback
        try:
            # Step 1: Generate initial script and code from Gemini
            if input_type == "Text Idea" and idea:
                with st.spinner("Generating initial script and code from idea..."):
                    video_data, script = generate_video(idea=idea)
            elif input_type == "Upload PDF" and uploaded_file is not None:
                with st.spinner("Generating initial script and code from PDF..."):
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".pdf"
                    ) as temp_pdf:
                        temp_pdf.write(uploaded_file.getvalue())
                        pdf_path = temp_pdf.name
                        files_to_cleanup.add(pdf_path)
                    video_data, script = generate_video(pdf_path=pdf_path)
            else:
                st.error("Please provide an idea or upload a PDF.")
                return

            if not video_data or not script:
                st.error("Failed to generate initial script/code from Gemini.")
                return

            # Step 2: Generate audio and subtitles from the script
            with st.spinner("Generating audio and subtitles..."):
                logging.info("Generating audio and subtitles for the script.")
                try:
                    # Unpack both audio and subtitle file paths
                    audio_file, subtitle_file = generate_audio(script)
                    if audio_file:
                        files_to_cleanup.add(audio_file)
                    if subtitle_file:
                        files_to_cleanup.add(subtitle_file)
                except ValueError as e:
                    st.warning(
                        f"Could not generate audio: {e}. Proceeding without audio/subtitles."
                    )
                    audio_file, subtitle_file = None, None

            current_manim_code = video_data["manim_code"]
            current_script = script
            current_audio_file = audio_file
            current_subtitle_file = subtitle_file

            # Step 3: Attempt to render the video, with fallback retries
            for attempt in range(max_retries + 1):
                try:
                    with st.spinner(f"Attempt {attempt + 1}: Creating Manim video..."):
                        logging.info(f"Attempt {attempt + 1} to create Manim video.")
                        final_video = create_manim_video(
                            video_data,
                            current_manim_code,
                            audio_file=current_audio_file,
                            subtitle_file=current_subtitle_file,
                        )
                    logging.info("Manim video creation successful.")
                    break  # Exit the loop on success
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    error_output = e.stderr if hasattr(e, "stderr") else str(e)
                    logging.error(f"Manim execution failed on attempt {attempt + 1}.")
                    st.warning(
                        f"Attempt {attempt + 1} failed. Manim error:\n```\n{error_output}\n```"
                    )

                    if attempt < max_retries:
                        st.info("Attempting to fix the code using fallback...")
                        logging.info("Calling fallback Gemini to fix code.")

                        fixed_video_data, fixed_script = fix_manim_code(
                            faulty_code=current_manim_code,
                            error_message=error_output,
                            original_context=original_context,
                        )

                        if fixed_video_data and fixed_script is not None:
                            st.success(
                                "Fallback successful! Retrying video generation with fixed code."
                            )
                            logging.info("Fallback successful. Received fixed code.")
                            current_manim_code = fixed_video_data["manim_code"]

                            # If narration changed, regenerate audio and subtitles
                            if fixed_script != current_script and fixed_script:
                                st.info(
                                    "Narration script was updated. Regenerating audio and subtitles..."
                                )
                                current_script = fixed_script
                                try:
                                    new_audio, new_subtitle = generate_audio(
                                        current_script
                                    )
                                    if new_audio:
                                        files_to_cleanup.add(new_audio)
                                    if new_subtitle:
                                        files_to_cleanup.add(new_subtitle)
                                    current_audio_file = new_audio
                                    current_subtitle_file = new_subtitle
                                except ValueError as audio_e:
                                    st.warning(
                                        f"Could not generate new audio: {audio_e}."
                                    )
                                    current_audio_file, current_subtitle_file = (
                                        None,
                                        None,
                                    )
                            else:
                                logging.info("Fallback kept the original narration.")
                        else:
                            st.error("Fallback failed to fix the code. Stopping.")
                            final_video = None
                            break
                    else:
                        st.error(
                            f"Manim failed after {max_retries + 1} attempts. Could not generate video."
                        )
                        final_video = None
                except Exception as e:
                    st.error(
                        f"An unexpected error occurred during video creation: {str(e)}"
                    )
                    logging.exception(
                        "Unexpected error during create_manim_video call."
                    )
                    final_video = None
                    break

            # Step 4: Display the final result
            if final_video and os.path.exists(final_video):
                st.success("Video generated successfully!")
                st.video(final_video)
                st.write("Generated Narration:")
                st.text_area(
                    "Narration",
                    current_script if current_script else "No narration was generated.",
                    height=150,
                )
            elif not final_video and attempt >= max_retries:
                # This message is shown if all retries failed
                st.error("Could not generate the video after multiple attempts.")
            elif not final_video:
                # A general failure message
                st.error("Video generation was unsuccessful.")
            else:
                st.error("Error: Generated video file not found after processing.")
                logging.error(f"Final video file '{final_video}' not found.")

        except Exception as e:
            st.error(f"An unexpected and critical error occurred: {str(e)}")
            logging.exception("Unhandled exception in main generation block.")
        finally:
            # Step 5: Clean up all generated temporary files
            logging.info(f"Cleaning up {len(files_to_cleanup)} temporary files.")
            for f_path in files_to_cleanup:
                if f_path and os.path.exists(f_path):
                    try:
                        os.remove(f_path)
                        logging.info(f"Removed temporary file: {f_path}")
                    except OSError as e:
                        logging.error(f"Error removing temporary file {f_path}: {e}")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("---")

    st.markdown(
        """
        ### Want to help improve this app?
        - Give good Manim Examples and make PRs in guide.md, find it in repo [GitHub](https://github.com/mostlykiguess/Manimator)
        - Report issues on [GitHub Issues](https://github.com/mostlykiguess/Manimator/issues)
        - Email problematic prompts to me 
        """
    )


if __name__ == "__main__":
    main()
