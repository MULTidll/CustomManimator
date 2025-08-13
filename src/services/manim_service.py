import re
import subprocess
import os
import glob
import logging
import platform


def get_scene_name(manim_code):
    """Extracts the scene class name from Manim code."""
    # This regex looks for 'class YourSceneName(Scene):' or 'class YourSceneName(ThreeDScene):'
    match = re.search(
        r"class\s+(\w+)\s*\(\s*(?:ThreeD|Multi)?[Ss]cene\s*\)", manim_code
    )
    if match:
        return match.group(1)
    raise ValueError("No Scene class found in generated code")


def sanitize_path_for_ffmpeg(path: str) -> str:
    if platform.system() == "Windows":
        # For Windows
        return path.replace("\\", "\\\\").replace(":", "\\:")
    else:
        # For Linux/macOS
        return (
            path.replace("'", "'\\''")
            .replace(":", "\\:")
            .replace(",", "\\,")
            .replace("[", "\\[")
            .replace("]", "\\]")
        )


def create_manim_video(video_data, manim_code, audio_file=None, subtitle_file=None):
    logging.info("Starting to create Manim video")
    with open("generated_video.py", "w", encoding="utf-8") as f:
        f.write(manim_code)

    scene_name = get_scene_name(manim_code)
    logging.info(f"Identified scene name: {scene_name}")

    command = ["manim", "-qh", "generated_video.py", scene_name]
    logging.info(f"Running Manim with command: {' '.join(command)}")

    # Use capture_output=True to get stderr for better error reporting
    manim_process = subprocess.run(command, check=True, capture_output=True, text=True)
    if manim_process.returncode != 0:
        logging.error(f"Manim failed with stderr:\n{manim_process.stderr}")
        raise subprocess.CalledProcessError(
            manim_process.returncode, command, stderr=manim_process.stderr
        )

    video_path = os.path.join(
        "media", "videos", "generated_video", "1080p60", f"{scene_name}.mp4"
    )
    if not os.path.exists(video_path):
        logging.error(f"No rendered video found at: {video_path}")
        raise FileNotFoundError(f"No rendered video found for scene {scene_name}")

    input_video = video_path
    final_output = "final_output.mp4"
    extended_video_temp = "extended_video.mp4"

    if audio_file and os.path.exists(audio_file):
        logging.info(f"Audio file found: {audio_file}")

        video_duration_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            input_video,
        ]
        audio_duration_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            audio_file,
        ]

        video_duration = float(
            subprocess.check_output(video_duration_cmd).decode("utf-8").strip()
        )
        audio_duration = float(
            subprocess.check_output(audio_duration_cmd).decode("utf-8").strip()
        )

        logging.info(
            f"Video duration: {video_duration}s, Audio duration: {audio_duration}s"
        )

        # If audio is longer, extend the video with a freeze frame of the last frame
        if audio_duration > video_duration:
            logging.info(
                "Audio is longer than video, extending video with freeze frame."
            )

            extend_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                input_video,
                "-vf",
                f"tpad=stop_mode=clone:stop_duration={audio_duration - video_duration}",
                "-c:v",
                "libx264",
                extended_video_temp,
            ]

            logging.info(f"Extending video with command: {' '.join(extend_cmd)}")
            subprocess.run(extend_cmd, check=True, capture_output=True, text=True)
            input_video = extended_video_temp  # The extended video is now our input

    # merge
    merge_cmd = ["ffmpeg", "-y", "-i", input_video]

    if audio_file and os.path.exists(audio_file):
        merge_cmd.extend(["-i", audio_file])

    filter_complex = []
    maps = ["-map", "0:v:0"]
    if audio_file and os.path.exists(audio_file):
        maps.extend(["-map", "1:a:0"])

    # Add subtitle
    if subtitle_file and os.path.exists(subtitle_file):
        sanitized_path = sanitize_path_for_ffmpeg(os.path.abspath(subtitle_file))
        filter_complex.append(f"ass='{sanitized_path}'")

    if filter_complex:
        merge_cmd.extend(["-vf", ",".join(filter_complex)])

    merge_cmd.extend(maps)
    merge_cmd.extend(["-c:v", "libx264", "-c:a", "aac", "-shortest", final_output])

    logging.info(f"Merging with final command: {' '.join(merge_cmd)}")
    subprocess.run(merge_cmd, check=True, capture_output=True, text=True)

    if os.path.exists(extended_video_temp):
        os.remove(extended_video_temp)
        logging.info("Removed temporary extended video file.")
    if os.path.exists("generated_video.py"):
        os.remove("generated_video.py")
        logging.info("Removed generated_video.py")

    logging.info(f"Final video created at: {final_output}")
    return final_output
