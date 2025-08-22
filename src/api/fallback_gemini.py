import os
import re
from google import genai
from google.genai import types as genai_types
import logging
from .gemini import base_prompt_instructions

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

FALLBACK_SYSTEM_PROMPT = """You are an expert Manim programmer specializing in fixing broken Manim code and creating visually striking 60-second animations, strictly following Manim Community v0.19.0 standards.

CRITICAL TIMING REQUIREMENTS:
- **Total Duration:** Exactly 300 seconds (5 minute)
- **Narration:** Exactly 150-160 words (average speaking pace: 2.5 words per second)
- **Animation Structure:** Use this timing framework:
  * Introduction: 8-10 seconds
  * Main content: 45–60 seconds (3-4 major segments)
  * Conclusion/summary: 60-75 seconds (provide recap, a takeaway and end memorably)
- **Synchronization:** Each narration sentence should correspond to 3-5 seconds of animation

Core Requirements:
- **API Version:** Use only Manim Community v0.19.0 API
- **Vectors & Math:** Use 3D vectors (np.array([x, y, 0])) and ensure correct math operations
- **Matrix Visualization:** Use MathTex for matrices: r'\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}'
- **Star Usage:** Use Star(n=5, ...) not n_points
- **Error Prevention:** Always validate Scene class exists; avoid 3D scenes
- **Visual Style:** Create vibrant, dynamic animations with smooth transitions

IMPORTANT: Your response must be formatted with clear delimiters:
- Start Manim code with: ### MANIM CODE:
- Start narration with: ### NARRATION:
- End response after narration (no additional text)
"""


def fix_manim_code(faulty_code: str, error_message: str, original_context: str):
    """
    Enhanced fallback function with Google Search integration.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logging.error("GEMINI_API_KEY not found in environment variables for fallback.")
        return None, None

    client = genai.Client(api_key=api_key)

    # Enhanced fallback prompt with better structure and error analysis
    fix_prompt_text = f"""
TASK: Fix the broken Manim code that failed with a specific error.

### ORIGINAL REQUEST:
{original_context}

### BROKEN MANIM CODE:
```python
{faulty_code}
```

### ERROR ENCOUNTERED:
```
{error_message}
```

### ANALYSIS INSTRUCTIONS:
1. **Error Analysis**: Examine the error message carefully. Common issues include:
   - Import errors (missing 'from manim import *' or 'import numpy as np')
   - Scene class not found (class must inherit from Scene)
   - Invalid Manim methods or syntax
   - Vector dimension mismatches (use np.array([x, y, 0]))
   - Animation object validation errors
   - Timing issues (ensure total duration = 60 seconds)

2. **Google Search**: Use Google Search to find:
   - Recent Manim Community v0.19.0 API changes
   - Specific error message solutions
   - Updated method signatures or deprecated features
   - Working examples of similar animations

3. **Code Fixing Strategy**:
   - Keep the original animation concept intact
   - Fix only what's necessary to resolve the error
   - Maintain 60-second duration and 120-150 word narration
   - Ensure all imports are present
   - Validate Scene class exists and is properly named
   - Use only verified Manim methods from the allowed list

4. **Quality Checks**:
   - Verify vector operations use 3D format: np.array([x, y, 0])
   - Check all self.play() calls have valid animation objects
   - Ensure run_time and self.wait() sum to exactly 60 seconds
   - Count narration words (must be 120-150)

### OUTPUT FORMAT:
Provide your response in exactly this format:

### MANIM CODE:
[Insert the complete, fixed Manim code here - include all imports and Scene class]

### NARRATION:
[Insert the narration script here - exactly 120-150 words, synchronized with animations]

### REQUIREMENTS TO FOLLOW:
{base_prompt_instructions}
"""

    contents = [fix_prompt_text]

    logging.info("Attempting to fix Manim code via fallback...")
    try:
        grounding_tool = genai_types.Tool(google_search=genai_types.GoogleSearch())

        generation_config = genai_types.GenerateContentConfig(
            tools=[grounding_tool],
            temperature=0.4,  # lower coz grounding
            system_instruction=FALLBACK_SYSTEM_PROMPT,
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,  # type: ignore
            config=generation_config,
        )
        if response:
            # print(response)
            try:
                content = response.text
                logging.info("Received response from fallback attempt.")

                if "### NARRATION:" in content:  # type: ignore
                    manim_code, narration = content.split("### NARRATION:", 1)  # type: ignore
                    manim_code = (
                        re.sub(r"```python", "", manim_code).replace("```", "").strip()
                    )
                    narration = narration.strip()

                    if "from manim import *" not in manim_code:
                        logging.warning(
                            "Adding missing 'from manim import *' (fallback fix)."
                        )
                        manim_code = (
                            "from manim import *\nimport numpy as np\n" + manim_code
                        )
                    elif "import numpy as np" not in manim_code:
                        logging.warning(
                            "Adding missing 'import numpy as np' (fallback fix)."
                        )
                        lines = manim_code.splitlines()
                        for i, line in enumerate(lines):
                            if "from manim import *" in line:
                                lines.insert(i + 1, "import numpy as np")
                                manim_code = "\n".join(lines)
                                break

                    logging.info(
                        "Successfully parsed fixed code and narration from fallback."
                    )
                    return {
                        "manim_code": manim_code,
                        "output_file": "output.mp4",
                    }, narration
                else:
                    logging.warning(
                        "Delimiter '### NARRATION:' not found in fallback response. Attempting fallback extraction."
                    )
                    code_match = re.search(r"```python(.*?)```", content, re.DOTALL)  # type: ignore
                    if code_match:
                        manim_code = code_match.group(1).strip()
                        narration_part = content.split("```", 2)[-1].strip()
                        narration = narration_part if len(narration_part) > 20 else ""
                        if not narration:
                            logging.warning(
                                "Fallback narration extraction resulted in empty or very short text (fallback fix)."
                            )
                        else:
                            logging.info(
                                "Successfully parsed code and narration using fallback regex (fallback fix)."
                            )

                        if "from manim import *" not in manim_code:
                            logging.warning(
                                "Adding missing 'from manim import *' (fallback fix, regex path)."
                            )
                            manim_code = (
                                "from manim import *\nimport numpy as np\n" + manim_code
                            )
                        elif "import numpy as np" not in manim_code:
                            logging.warning(
                                "Adding missing 'import numpy as np' (fallback fix, regex path)."
                            )
                            lines = manim_code.splitlines()
                            for i, line in enumerate(lines):
                                if "from manim import *" in line:
                                    lines.insert(i + 1, "import numpy as np")
                                    manim_code = "\n".join(lines)
                                    break

                        logging.info(
                            "Successfully parsed fixed code using fallback extraction."
                        )
                        return {
                            "manim_code": manim_code,
                            "output_file": "output.mp4",
                        }, narration
                    else:
                        logging.error(
                            "Fallback extraction failed: No Python code block found in fallback response."
                        )
                        logging.debug(
                            f"Fallback content without code block:\n{content}"
                        )
                        return None, None

            except ValueError:
                logging.error("Could not extract text from the fallback response.")
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    logging.error(
                        f"Fallback content generation blocked. Reason: {response.prompt_feedback.block_reason.name}"
                    )
                return None, None
            except Exception as e:
                logging.exception(f"Error processing fallback response: {e}")
                return None, None
        else:
            logging.error("No response received from Gemini during fallback attempt.")
            return None, None

    except Exception as e:
        logging.exception(f"Error calling Gemini API during fallback: {e}")
        return None, None
