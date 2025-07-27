import re
from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv
import os
import pathlib
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global System Prompt ---
SYSTEM_PROMPT = """You are an expert Manim programmer specializing in creating crazy, cutting-edge, and visually striking animations based on user prompts or documents, strictly following Manim Community v0.19.0 standards.

Core Requirements:
- **API Version:** Use only Manim Community v0.19.0 API.
- **Vectors & Math:** Use 3D vectors (`np.array([x, y, 0])`) and ensure correct math operations.
- **Allowed Methods:** Strictly use the verified list of Manim methods provided in the detailed instructions. No external images.
- **        "\n   - self.play(), self.wait(), Create(), Write(), Transform(), FadeIn(), FadeOut(), Add(), Remove(), MoveAlongPath(), Rotating(), Circumscribe(), Indicate(), FocusOn(), Shift(), Scale(), MoveTo(), NextTo(), Axes(), Plot(), LineGraph(), BarChart(), Dot(), Line(), Arrow(), Text(), Tex(), MathTex(), VGroup(), Mobject.animate, self.camera.frame.animate"
- **Matrix Visualization:** Use `MathTex` for displaying matrices in the format `r'\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}'`.
- **Duration:** The total animation duration MUST be exactly 30 seconds.
-**Error handling**:"An unexpected error occurred during video creation: No Scene class found in generated code, This error SHOULD NEVER occur. Make sure to validate the code before returning it. If this error occurs, please log the error and return None for both manim_code and narration.Make sure you don't do 3Dscene coz that gives this error"
- **Engagement:** Create visually stunning and crazy animations that push creative boundaries. Use vibrant colors, dynamic movements, and unexpected transformations.
- **Text Handling:** Fade out text and other elements as soon as they are no longer needed, ensuring a smooth transition.
- **Synchronization:** Align animation pacing (`run_time`, `wait`) roughly with the narration segments.
- **Output Format:** Return *only* the Python code and narration script, separated by '### MANIM CODE:' and '### NARRATION:' delimiters. Adhere strictly to this format.
- **Code Quality:** Generate error-free, runnable code with necessary imports (`from manim import *`, `import numpy as np`) and exactly one Scene class. Validate objects and animation calls.
"""

# --- Detailed Instructions ---
base_prompt_instructions = (
        "\nFollow these requirements strictly:"
        "\n1. Use only Manim Community v0.19.0 API"
        "\n2. Vector operations:"
        "\n   - All vectors must be 3D: np.array([x, y, 0])"
        "\n   - Matrix multiplication: result = np.dot(matrix, vector[:2])"
        "\n   - Append 0 for Z: np.append(result, 0)"
        "\n3. Matrix visualization:"
        "\n   - Use MathTex for display"
        "\n   - Format: r'\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}'"
        "\n4. Use only verified Manim methods:"
        "\n   - self.play(), self.wait(), Create(), Write(), Transform(), FadeIn(), FadeOut(), Add(), Remove(), MoveAlongPath(), Rotating(), Circumscribe(), Indicate(), FocusOn(), Shift(), Scale(), MoveTo(), NextTo(), Axes(), Plot(), LineGraph(), BarChart(), Dot(), Line(), Arrow(), Text(), Tex(), MathTex(), VGroup(), Mobject.animate, self.camera.frame.animate"
        "\n5. DO NOT USE IMAGES IMPORTS."
        "\n6. Make the video crazy and innovative by:"
        "\n   - Fading out text and other elements gracefully once they are no longer needed"
        "\n   - Adding creative interactive elements like arrows, labels, and transitions"
        "\n   - Incorporating graphs/plots (Axes, Plot, LineGraph, BarChart) where appropriate"
        "\n   - Leveraging smooth transitions and varied pacing to keep the viewer engaged."
        "\n7. Ensure the video is error-free by:"
        "\n   - Validating all objects before animations"
        "\n   - Handling exceptions gracefully (in generated code if applicable)"
        "\n   - Ensuring operands for vector operations match in shape to avoid broadcasting errors"
        "\n8. Validate that every arrow creation ensures its start and end points are distinct to prevent normalization errors."
        "\n9. Use longer scenes (e.g., 5-6 seconds per major step) for complex transformations and shorter scenes for simple animations, with a total duration of exactly 30 seconds."
        "\n10. Align the narration script with the animation pace for seamless storytelling."
        "\n11. Ensure all objects in self.play() are valid animations (e.g., `Create(obj)`, `obj.animate.shift(UP)`)."
        "\n12. Use Mobject.animate for animations involving Mobject methods."
        "\n13. CRITICAL: DO NOT USE BARCHATS, LINEGRAPHS, OR PLOTTING WITHOUT EXPLICIT INSTRUCTIONS."
        "\n14. Provide creative and sometimes crazy Manim video scripts that push the conventional boundaries."
        "\n15. **Synchronization:** Structure the narration and Manim code for better synchronization:"
        "\n    - Keep narration segments concise and directly tied to the visual elements."
        "\n    - Use `self.wait(duration)` in the Manim code to match natural pauses in narration."
        "\n    - Adjust `run_time` in `self.play()` calls to match the speaking duration of the associated narration."
        "\n    - Ensure the animation and narration sum to exactly 30 seconds."
        "\n### MANIM CODE:\n"
        "Provide only valid Python code using Manim Community v0.19.0 to generate the video animation.\n\n"
        "### NARRATION:\n"
        "Provide a concise narration script for the video that aligns with the Manim code's pacing and visuals.DO NOT give timestamps.\n\n"
    )


def load_manim_examples():
    guide_path = pathlib.Path(__file__).parent / "guide.md"
    if not guide_path.exists():
        logging.warning(f"Manim examples guide not found at {guide_path}")
        return ""

    logging.info(f"Loading Manim examples from {guide_path}")
    return guide_path.read_text(encoding="utf-8")


def generate_video(idea: str | None = None, pdf_path: str | None = None):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logging.error("GEMINI_API_KEY not found in environment variables")
        raise Exception("GEMINI_API_KEY not found in environment variables")

    if not idea and not pdf_path:
        raise ValueError("Either an idea or a pdf_path must be provided.")
    if idea and pdf_path:
        logging.warning("Both idea and pdf_path provided. Using pdf_path.")
        idea = None

    client = genai.Client(api_key=api_key)
    contents = []

    manim_examples = load_manim_examples()
    if manim_examples:
        examples_prompt = "Below are examples of Manim code that demonstrate proper usage patterns. Use these as reference when generating your animation:\n\n" + manim_examples
        contents.append(examples_prompt)
        logging.info("Added Manim examples from guide.md to prime the model")
    else:
        logging.warning("No Manim examples were loaded from guide.md")

    user_prompt_text = ""

    if pdf_path:
        pdf_file_path = pathlib.Path(pdf_path)
        if not pdf_file_path.exists():
             logging.error(f"PDF file not found at: {pdf_path}")
             raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

        logging.info(f"Reading PDF: {pdf_path}")
        pdf_data = pdf_file_path.read_bytes()
        pdf_part = genai_types.Part.from_bytes(data=pdf_data, mime_type='application/pdf')
        contents.append(pdf_part)

        user_prompt_text = f"Create a 30-second Manim video script summarizing the key points or illustrating a core concept from the provided PDF document. {base_prompt_instructions}"
        contents.append(user_prompt_text)

    elif idea:
        logging.info(f"Generating video based on idea: {idea[:50]}...")
        user_prompt_text = f"Create a 30-second Manim video script about '{idea}'. {base_prompt_instructions}"
        contents.append(user_prompt_text)

    logging.info("Sending request to Gemini API...")
    try:
        generation_config = genai_types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT
    )

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=generation_config
            )
    except Exception as e:
        logging.exception(f"Error calling Gemini API: {e}")
        raise Exception(f"Error calling Gemini API: {e}")

    if response:
        try:
            content = response.text
            logging.info("Received response from Gemini.")
        except ValueError:
             logging.warning("Could not extract text from the response. Response details:")
             logging.warning(response)
             if response.prompt_feedback and response.prompt_feedback.block_reason:
                 logging.error(f"Content generation blocked. Reason: {response.prompt_feedback.block_reason.name}")
                 raise Exception(f"Content generation blocked. Reason: {response.prompt_feedback.block_reason.name}")
             else:
                 logging.error("Failed to generate content. The response was empty or malformed.")
                 raise Exception("Failed to generate content. The response was empty or malformed.")

        if "### NARRATION:" in content:
            manim_code, narration = content.split("### NARRATION:", 1)
            manim_code = re.sub(r"```python", "", manim_code).replace("```", "").strip()
            narration = narration.strip()
            logging.info("Successfully parsed code and narration using delimiter.")

            if "from manim import *" not in manim_code:
                 logging.warning("Adding missing 'from manim import *'.")
                 manim_code = "from manim import *\nimport numpy as np\n" + manim_code
            elif "import numpy as np" not in manim_code:
                 logging.warning("Adding missing 'import numpy as np'.")
                 lines = manim_code.splitlines()
                 for i, line in enumerate(lines):
                     if "from manim import *" in line:
                         lines.insert(i + 1, "import numpy as np")
                         manim_code = "\n".join(lines)
                         break

            return {"manim_code": manim_code, "output_file": "output.mp4"}, narration
        else:
            logging.warning("Delimiter '### NARRATION:' not found. Attempting fallback extraction.")
            code_match = re.search(r'```python(.*?)```', content, re.DOTALL)
            if code_match:
                manim_code = code_match.group(1).strip()
                narration_part = content.split('```', 2)[-1].strip()
                narration = narration_part if len(narration_part) > 20 else ""
                if not narration:
                    logging.warning("Fallback narration extraction resulted in empty or very short text.")
                else:
                    logging.info("Successfully parsed code and narration using fallback regex.")

                if "from manim import *" not in manim_code:
                     logging.warning("Adding missing 'from manim import *' (fallback).")
                     manim_code = "from manim import *\nimport numpy as np\n" + manim_code
                elif "import numpy as np" not in manim_code:
                     logging.warning("Adding missing 'import numpy as np' (fallback).")
                     lines = manim_code.splitlines()
                     for i, line in enumerate(lines):
                         if "from manim import *" in line:
                             lines.insert(i + 1, "import numpy as np")
                             manim_code = "\n".join(lines)
                             break

                return {"manim_code": manim_code, "output_file": "output.mp4"}, narration
            else:
                 logging.error("Fallback extraction failed: No Python code block found in response.")
                 logging.debug(f"Content without code block:\n{content}")
                 raise Exception("The response does not contain the expected '### NARRATION:' delimiter or a valid Python code block.")

    else:
        logging.error("Error generating video content. No response received from Gemini.")
        raise Exception("Error generating video content. No response received.")
