import os
import re
import google.genai as genai
from google.genai import types as genai_types
import logging
from .gemini import SYSTEM_PROMPT, base_prompt_instructions

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fix_manim_code(faulty_code: str, error_message: str, original_context: str):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logging.error("GEMINI_API_KEY not found in environment variables for fallback.")
        return None, None

    client = genai.Client(api_key=api_key)

    fix_prompt_text = (
        f"The following Manim code, intended to '{original_context}', failed with an error.\n\n"
        "### FAULTY CODE:\n"
        f"```python\n{faulty_code}\n```\n\n"
        "### ERROR MESSAGE:\n"
        f"```\n{error_message}\n```\n\n"
        "### INSTRUCTIONS:\n"
        "1. Analyze the error message and the faulty code.\n"
        "2. Correct the code to fix the specific error reported.\n"
        "3. Ensure the corrected code still fulfills the original request and adheres strictly to *all* the requirements listed below.\n"
        "4. Pay close attention to vector dimensions, matrix operations, allowed Manim methods, and total duration (30 seconds).\n"
        "5. If the code logic changes significantly, update the narration accordingly.\n"
        "6. Return *only* the corrected code and narration using the '### MANIM CODE:' and '### NARRATION:' delimiters, just like the original request.\n\n"
        "### REQUIREMENTS (Apply these to the corrected code):\n"
        f"{base_prompt_instructions}" 
    )

    contents = [fix_prompt_text] 

    logging.info("Attempting to fix Manim code via fallback...")
    try:
        generation_config = genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT
        )
        
        response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=contents,
                config=generation_config
                )
        if response:
            try:
                content = response.text
                logging.info("Received response from fallback attempt.")
                
                if "### NARRATION:" in content:
                    manim_code, narration = content.split("### NARRATION:", 1)
                    manim_code = re.sub(r"```python", "", manim_code).replace("```", "").strip()
                    narration = narration.strip()

                    if "from manim import *" not in manim_code:
                         logging.warning("Adding missing 'from manim import *' (fallback fix).")
                         manim_code = "from manim import *\nimport numpy as np\n" + manim_code
                    elif "import numpy as np" not in manim_code:
                         logging.warning("Adding missing 'import numpy as np' (fallback fix).")
                         lines = manim_code.splitlines()
                         for i, line in enumerate(lines):
                             if "from manim import *" in line:
                                 lines.insert(i + 1, "import numpy as np")
                                 manim_code = "\n".join(lines)
                                 break

                    logging.info("Successfully parsed fixed code and narration from fallback.")
                    return {"manim_code": manim_code, "output_file": "output.mp4"}, narration
                else:
                    logging.warning("Delimiter '### NARRATION:' not found in fallback response. Attempting fallback extraction.")
                    code_match = re.search(r'```python(.*?)```', content, re.DOTALL)
                    if code_match:
                        manim_code = code_match.group(1).strip()
                        narration_part = content.split('```', 2)[-1].strip()
                        narration = narration_part if len(narration_part) > 20 else ""
                        if not narration:
                            logging.warning("Fallback narration extraction resulted in empty or very short text (fallback fix).")
                        else:
                            logging.info("Successfully parsed code and narration using fallback regex (fallback fix).")

                        if "from manim import *" not in manim_code:
                             logging.warning("Adding missing 'from manim import *' (fallback fix, regex path).")
                             manim_code = "from manim import *\nimport numpy as np\n" + manim_code
                        elif "import numpy as np" not in manim_code:
                             logging.warning("Adding missing 'import numpy as np' (fallback fix, regex path).")
                             lines = manim_code.splitlines()
                             for i, line in enumerate(lines):
                                 if "from manim import *" in line:
                                     lines.insert(i + 1, "import numpy as np")
                                     manim_code = "\n".join(lines)
                                     break

                        logging.info("Successfully parsed fixed code using fallback extraction.")
                        return {"manim_code": manim_code, "output_file": "output.mp4"}, narration
                    else:
                         logging.error("Fallback extraction failed: No Python code block found in fallback response.")
                         logging.debug(f"Fallback content without code block:\n{content}")
                         return None, None

            except ValueError:
                logging.error("Could not extract text from the fallback response.")
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                     logging.error(f"Fallback content generation blocked. Reason: {response.prompt_feedback.block_reason.name}")
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
