"""3.2: the cloud check (tools/cloud_check.py) passes, and really catches a missing package."""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))

import cloud_check


class CloudCheck(unittest.TestCase):
    def test_every_import_is_installed_on_streamlit_cloud(self):
        self.assertEqual(cloud_check.static_problems(), [])

    def test_the_whole_app_renders_with_only_the_requirements(self):
        problems, report = cloud_check.runtime_problems()
        self.assertEqual(problems, [])
        self.assertIn('foto di squadra', report)

    def test_an_unguarded_import_is_caught_a_guarded_one_is_not(self):
        source = 'import scipy\ntry:\n    import cv2\nexcept ImportError:\n    cv2 = None\n'
        tree = ast.parse(source)
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        imports = [n for n in ast.walk(tree) if isinstance(n, ast.Import)]
        self.assertEqual([cloud_check._in_try(n, parents) for n in imports], [False, True])

    def test_the_blocker_blocks_what_cloud_lacks(self):
        script = cloud_check.BLOCKER % {'allowed': sorted(cloud_check.allowed_imports()), 'local': [], 'root': str(ROOT)}
        result = subprocess.run([sys.executable, '-c', script+'import scipy'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Streamlit Cloud', result.stderr)


if __name__ == '__main__':
    unittest.main()
