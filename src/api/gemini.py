import re
from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv
import os
import pathlib
import logging
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class ManimOutput(BaseModel):
    manim_code: str
    narration: str


SYSTEM_PROMPT = """You are an expert Manim programmer specializing in creating visually striking 60-second animations based on user prompts or documents, strictly following Manim Community v0.19.0 standards. Your output MUST be a JSON object conforming to the provided schema.

CRITICAL TIMING REQUIREMENTS:
- **Total Duration:** Exactly 60 seconds (1 minute)
- **Narration:** Exactly 150-160 words (average speaking pace: 2.5 words per second)
- **Animation Structure:** Use this timing framework:
  * Introduction: 8-10 seconds
  * Main content: 40-45 seconds (3-4 major segments)
  * Conclusion/summary: 7-10 seconds
- **Synchronization:** Each narration sentence should correspond to 3-5 seconds of animation

Core Requirements:
- **API Version:** Use only Manim Community v0.19.0 API
- **Vectors & Math:** Use 3D vectors (np.array([x, y, 0])) and ensure correct math operations
- **Matrix Visualization:** Use MathTex for matrices: r'\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}'
- **Star Usage:** Use Star(n=5, ...) not n_points
- **Error Prevention:** Always validate Scene class exists; avoid 3D scenes
- **Visual Style:** Create vibrant, dynamic animations with smooth transitions
- **Output Format:** JSON with "manim_code" and "narration" keys
"""
# Detailed Instructions
base_prompt_instructions = (
    "\nSTRICT TIMING REQUIREMENTS:"
    "\n1. **Video Duration:** Exactly 60 seconds total"
    "\n2. **Narration Constraints:**"
    "\n   - Exactly 150-160 words (no more, no less)"
    "\n   - Speaking pace: 2.5 words per second"
    "\n   - Use short, clear sentences (8-12 words each)"
    "\n   - Include natural pauses between major concepts"
    "\n3. **Animation Timing Structure:**"
    "\n   - Use self.wait() to match narration pauses"
    "\n   - run_time in self.play() should match sentence duration"
    "\n   - Fade out elements after 3-5 seconds to avoid clutter"
    "\n   - Example timing: self.play(Create(obj), run_time=3), self.wait(1)"
    "\nTECHNICAL REQUIREMENTS:"
    "\n4. Use only Manim Community v0.19.0 API"
    "\n5. Vector operations (3D vectors): np.array([x, y, 0])"
    "\n6. Matrix display: MathTex(r'\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}')"
    "\n7. Verified methods only: Create(), Write(), Transform(), FadeIn(), FadeOut(), "
    "\n   Add(), Remove(), MoveAlongPath(), Rotating(), Circumscribe(), Indicate(), "
    "\n   FocusOn(), Shift(), Scale(), MoveTo(), NextTo(), Axes(), Plot(), LineGraph(), "
    "\n   BarChart(), Dot(), Line(), Arrow(), Text(), Tex(), MathTex(), VGroup()"
    "\n8. Star shapes: Star(n=5, ...) not n_points"
    "\n9. NO image imports or 3D scenes"
    "\n10. There is no .to_center() method so please don't use that"
    "\nVISUAL & CONTENT GUIDELINES:"
    "\n10. Create 4-5 distinct visual segments matching narration flow"
    "\n11. Use vibrant colors and smooth transitions"
    "\n12. Fade out text/objects when no longer needed"
    "\n13. Include interactive elements: arrows, labels, highlights"
    "\n14. Validate all objects before animation calls"
    "\n15. Use longer run_times (4-6s) for complex animations, shorter (2-3s) for simple ones"
    "\nCODE STRUCTURE TEMPLATE:"
    "\n16. Always follow this timing pattern:"
    "\n    ```python"
    "\n    class VideoScene(Scene):"
    "\n        def construct(self):"
    "\n            # Intro (8-10s): Title + brief setup"
    "\n            title = Text('Title')"
    "\n            self.play(Write(title), run_time=3)"
    "\n            self.wait(2)  # Pause for narration"
    "\n            self.play(FadeOut(title), run_time=2)"
    "\n            "
    "\n            # Main content (40-45s): 3-4 segments"
    "\n            # Segment 1 (10-12s)"
    "\n            # Segment 2 (10-12s)  "
    "\n            # Segment 3 (10-12s)"
    "\n            # Segment 4 (8-10s)"
    "\n            "
    "\n            # Conclusion (7-10s): Summary + fade out"
    "\n    ```"
    "\nNARRATION STRUCTURE:"
    "\n17. Follow this word count breakdown:"
    "\n    - Introduction: 15-25 words (8-10 seconds)"
    "\n    - Main content: 70-85 words (36-40 seconds)"
    "\n    - Conclusion: 20-25 words (8-10 seconds)"
    "\n    - Natural pauses: 3-5 seconds total"
    "\n18. Use active voice, present tense"
    "\n19. Include transition phrases: 'Now let's see...', 'Next, we'll explore...'"
    "\n20. End with a strong concluding statement"
    "\nQUALITY ASSURANCE:"
    "\n21. Count words in narration before finalizing (must be 120-150)"
    "\n22. Calculate total animation time (self.play + self.wait = 60s)"
    "\n23. Ensure Scene class exists and imports are correct"
    "\n24. Test that all animation objects are valid before use"
    "\n25. No broadcasting errors in vector operations"
    "\n26. Distinct start/end points for arrows to prevent normalization errors"
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
        examples_prompt = (
            "Below are examples of Manim code that demonstrate proper usage patterns. Use these as reference when generating your animation:\n\n"
            + manim_examples
        )
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
        pdf_part = genai_types.Part.from_bytes(
            data=pdf_data, mime_type="application/pdf"
        )
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
            response_mime_type="application/json",
            response_schema=ManimOutput,
            system_instruction=SYSTEM_PROMPT,
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=contents, config=generation_config
        )
    except Exception as e:
        logging.exception(f"Error calling Gemini API: {e}")
        raise Exception(f"Error calling Gemini API: {e}")

    if response:
        try:
            parsed_output = response.parsed
            if not parsed_output or not isinstance(parsed_output, ManimOutput):
                logging.error("Failed to parse structured output from Gemini.")
                raise Exception("Failed to parse structured output from Gemini.")

            manim_code = parsed_output.manim_code
            narration = parsed_output.narration
            logging.info("Successfully parsed structured output from Gemini.")

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
        except (ValueError, AttributeError) as e:
            logging.warning(
                f"Could not parse the response. Error: {e}. Response details:"
            )
            logging.warning(response)
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                logging.error(
                    f"Content generation blocked. Reason: {response.prompt_feedback.block_reason.name}"
                )
                raise Exception(
                    f"Content generation blocked. Reason: {response.prompt_feedback.block_reason.name}"
                )
            else:
                logging.error(
                    "Failed to generate content. The response was empty or malformed."
                )
                raise Exception(
                    "Failed to generate content. The response was empty or malformed."
                )
    else:
        logging.error(
            "Error generating video content. No response received from Gemini."
        )
        raise Exception("Error generating video content. No response received.")
