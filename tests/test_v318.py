"""3.18: sturdier app (page guard, memory for videos)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import robust
except ModuleNotFoundError:                       # robust imports streamlit; CI without it skips
    robust = None


@unittest.skipIf(robust is None, 'streamlit not installed')
class Memory(unittest.TestCase):
    def test_only_the_newest_heavy_outputs_stay(self):
        state = {'png_Full Time': b'x'*100, 'squad': [{'name': 'TEU'}]}
        for i in range(5):
            state[f'out_{i}'] = {'signature': i, 'data': bytes(1_200_000)}
            robust.trim_outputs(state, keep=3)
        self.assertEqual(sorted(k for k in state if k.startswith('out_')), ['out_2', 'out_3', 'out_4'])
        self.assertIn('png_Full Time', state)                          # small things are never touched
        self.assertIn('squad', state)

    def test_budget_and_replaced_values(self):
        state = {}
        state['a'] = bytes(3_000_000)
        robust.trim_outputs(state, keep=5, budget=5_000_000)
        state['b'] = bytes(3_000_000)
        robust.trim_outputs(state, keep=5, budget=5_000_000)
        self.assertEqual(sorted(k for k in state if not k.startswith('_')), ['b'])     # over budget: the older goes
        state['b'] = bytes(1_500_000)                                   # made again: counts as the newest
        state['c'] = bytes(1_500_000)
        robust.trim_outputs(state, keep=5, budget=5_000_000)
        self.assertEqual(sorted(k for k in state if not k.startswith('_')), ['b', 'c'])

    def test_streamlit_control_flow_passes(self):
        class RerunException(Exception):
            pass

        class StopException(Exception):
            pass
        self.assertTrue(robust.is_control(RerunException()))
        self.assertTrue(robust.is_control(StopException()))
        self.assertFalse(robust.is_control(ValueError('file strano')))


if __name__ == '__main__':
    unittest.main()
