import unittest

from src.api.fallback_gemini import fix_manim_code

class TestFallbackOnly(unittest.TestCase):
    def test_fallback_with_broken_code(self):
        broken_code = "from manim import *\nclass Broken(Scene):\n    def construct(self):\n        self.play(Write(Text('Oops!'))"
        error_message = "SyntaxError: unexpected EOF while parsing"
        original_context = "Test fallback with broken code"
        fixed_video_data, fixed_script = fix_manim_code(
            faulty_code=broken_code,
            error_message=error_message,
            original_context=original_context
        )
        print("Fixed video data:", fixed_video_data)
        print("Fixed script:", fixed_script)
        self.assertTrue(fixed_video_data is not None or fixed_script is None)

if __name__ == "__main__":
    unittest.main()