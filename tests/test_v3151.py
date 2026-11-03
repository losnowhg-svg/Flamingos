"""3.15.1: saves at a calm pace (one at most every few seconds, nothing lost)."""
import sys
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))

import shared_store as ss
from fake_github import FakeGitHub


class Pace(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGitHub()
        self.meta = {}
        self.factory = lambda: ss.GitHubStore('buono', self.fake.repo, transport=self.fake)

    def snap(self, vote, page='Figurine'):
        return ss.snapshot({'pagelle_memory': {'TEU': {'voto': vote}}}, page, 'LUCA')

    def last_vote(self):
        return ss.restore(self.factory().load()[0])['pagelle_memory']['TEU']['voto']

    def test_a_burst_of_changes_is_two_saves_and_the_last_one_wins(self):
        saver = ss.Saver(self.meta, throttle=.4)
        for vote in ('6', '6½', '7', '7½', '8'):
            saver.submit(self.factory, self.snap(vote))
            time.sleep(.02)
        self.assertTrue(saver.pending)
        self.assertTrue(saver.wait(5))
        self.assertEqual(len(self.fake.commits), 2)          # the first at once, the other four folded into one
        self.assertEqual(self.last_vote(), '8')
        self.assertEqual(self.meta['sha'], self.fake.files['lavoro.json'][1])
        self.assertFalse(saver.pending)

    def test_the_last_change_leaves_even_if_nobody_touches_the_app(self):
        saver = ss.Saver(self.meta, throttle=.3)
        saver.submit(self.factory, self.snap('6'))
        time.sleep(.05)
        saver.submit(self.factory, self.snap('9'))
        self.assertEqual(saver.wait(5), True)
        self.assertEqual(self.last_vote(), '9')

    def test_a_quiet_moment_means_the_next_save_leaves_at_once(self):
        saver = ss.Saver(self.meta, throttle=.2)
        saver.submit(self.factory, self.snap('6'))
        saver.wait(5)
        time.sleep(.3)
        started = time.monotonic()
        saver.submit(self.factory, self.snap('7'))
        saver.wait(5)
        self.assertLess(time.monotonic()-started, .15)
        self.assertEqual(len(self.fake.commits), 2)

    def test_events_and_uploads_are_kept_when_folded(self):
        import hashlib
        saver = ss.Saver(self.meta, throttle=.3)
        saver.submit(self.factory, self.snap('6'))
        logo = b'\x89PNG'+bytes(10)
        asset = 'logo:'+hashlib.sha256(logo).hexdigest()
        first = self.snap('7')
        first['event'] = 'tornato alla versione di Marco'
        first['assets'][asset] = {'kind': 'logo', 'name': 'Sponsor'}
        saver.submit(self.factory, first, [(asset, logo)])
        later = self.snap('8')
        later['assets'][asset] = {'kind': 'logo', 'name': 'Sponsor'}
        saver.submit(self.factory, later)
        saver.wait(5)
        self.assertIn('archivio/logo-'+asset[5:], self.fake.files)
        self.assertEqual(self.fake.commits[-1][1], 'Lavoro di LUCA (Figurine · tornato alla versione di Marco)')
        self.assertEqual(self.last_vote(), '8')

    def test_cancel_forgets_what_has_not_left(self):
        saver = ss.Saver(self.meta, throttle=.4)
        saver.submit(self.factory, self.snap('6'))
        time.sleep(.05)
        saver.submit(self.factory, self.snap('2'))           # a change, then the friends' work is taken
        saver.cancel()
        saver.wait(5)
        self.assertEqual(len(self.fake.commits), 1)
        self.assertEqual(self.last_vote(), '6')

    def test_errors_are_reported_and_retried_later(self):
        saver = ss.Saver(self.meta, throttle=.05)
        saver.submit(lambda: ss.GitHubStore('sbagliato', self.fake.repo, transport=self.fake), self.snap('6'))
        saver.wait(5)
        self.assertIn('Token', self.meta['error'])
        self.assertIsNone(self.meta['hash'])
        saver.submit(self.factory, self.snap('6'))
        saver.wait(5)
        self.assertIsNone(self.meta['error'])

    def test_one_thread_at_a_time(self):
        saver = ss.Saver(self.meta, throttle=.2)
        before = threading.active_count()
        for vote in '678':
            saver.submit(self.factory, self.snap(vote))
        self.assertLessEqual(threading.active_count()-before, 1)
        saver.wait(5)


if __name__ == '__main__':
    unittest.main()
