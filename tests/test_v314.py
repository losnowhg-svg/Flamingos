"""3.14: lavoro condiviso, the studio's work saved in a private repo so any friend can carry on."""
import datetime as dt
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))

import shared_store as ss
from fake_github import FakeGitHub


def store(fake, token='buono'):
    return ss.GitHubStore(token, fake.repo, transport=fake)


STATE = {'shared_match': {'opponent': 'GALBA F.C.', 'round': 6}, 'csi_matches': [
    {'home': 'GALBA F.C.', 'away': 'FLAMINGOS', 'date': dt.date(2026, 10, 29), 'score': (2, 4)}],
    'pagelle_memory': {'TEU': {'voto': '8½', 'gol': 2}}, 'figurina_card': {'data': b'\x89PNG'},
    'studio_template': 'Figurine', 'vault_command': {'x': 1}}


class Snapshot(unittest.TestCase):
    def test_round_trip_with_dates_and_only_shared_keys(self):
        snap = ss.snapshot(STATE, 'Figurine', 'luca', {}, now=dt.datetime(2026, 11, 1, 18, 40))
        self.assertNotIn('figurina_card', snap['state'])       # renders (bytes) are not shared
        self.assertNotIn('vault_command', snap['state'])       # internals neither
        back = ss.restore(json.loads(json.dumps(snap)))
        self.assertEqual(back['csi_matches'][0]['date'], dt.date(2026, 10, 29))
        self.assertEqual(back['csi_matches'][0]['score'], [2, 4])
        self.assertEqual(back['pagelle_memory']['TEU']['voto'], '8½')
        self.assertEqual(snap['author'], 'luca')

    def test_fingerprint_ignores_time_and_author(self):
        a = ss.snapshot(STATE, 'Figurine', 'luca', now=dt.datetime(2026, 11, 1, 18, 40))
        b = ss.snapshot(STATE, 'Figurine', 'marco', now=dt.datetime(2026, 11, 2, 9, 0))
        self.assertEqual(ss.fingerprint(a), ss.fingerprint(b))
        c = ss.snapshot(dict(STATE, pagelle_memory={}), 'Figurine')
        self.assertNotEqual(ss.fingerprint(a), ss.fingerprint(c))

    def test_unknown_versions_restore_nothing(self):
        self.assertEqual(ss.restore({'version': 99, 'state': {'squad': []}}), {})
        self.assertEqual(ss.restore(None), {})


class Store(unittest.TestCase):
    def test_save_load_and_history(self):
        fake = FakeGitHub()
        self.assertEqual(store(fake).load(), (None, None))
        snap = ss.snapshot(STATE, 'Figurine', 'LUCA')
        sha, theirs = store(fake).save(snap)
        self.assertIsNone(theirs)
        loaded, sha2 = store(fake).load()
        self.assertEqual((loaded['author'], sha2), ('LUCA', sha))
        store(fake).save(dict(snap, author='MARCO'), sha)
        self.assertEqual([m for _, m in fake.commits], ['Lavoro di LUCA (Figurine)', 'Lavoro di MARCO (Figurine)'])

    def test_two_friends_at_once_nothing_lost(self):
        fake = FakeGitHub()
        sha, _ = store(fake).save(ss.snapshot(STATE, 'Figurine', 'LUCA'))
        store(fake).save(ss.snapshot(STATE, 'Risultati', 'MARCO'), sha)          # Marco saves on top
        _, theirs = store(fake).save(ss.snapshot(STATE, 'Settimana', 'LUCA'), sha)   # Luca still has the old sha
        self.assertEqual(theirs['author'], 'MARCO')                               # told whose save he covered
        self.assertEqual(store(fake).load()[0]['page'], 'Settimana')
        self.assertEqual(len(fake.commits), 3)                                    # Marco's version is in the history

    def test_big_files_and_assets(self):
        fake = FakeGitHub()
        logo = b'\x89PNG' + bytes(1_200_000)
        asset_id = 'logo:'+hashlib.sha256(logo).hexdigest()
        path = store(fake).put_asset(asset_id, logo)
        store(fake).put_asset(asset_id, logo)                                     # twice: no error, one file
        self.assertEqual(path, 'archivio/logo-'+asset_id[5:])
        self.assertEqual(store(fake).get_asset(asset_id), logo)                   # over 1 MB: read raw
        fake.files[path] = (b'altro', 'x')
        with self.assertRaises(ss.StoreError):
            store(fake).get_asset(asset_id)
        with self.assertRaises(ss.StoreError):
            ss.asset_path('../../etc')

    def test_clear_errors(self):
        fake = FakeGitHub()
        with self.assertRaisesRegex(ss.StoreError, 'Token'):
            store(fake, 'sbagliato').load()
        with self.assertRaisesRegex(ss.StoreError, 'privato'):
            store(FakeGitHub(private=False)).check()
        with self.assertRaisesRegex(ss.StoreError, 'repo'):
            ss.GitHubStore('', 'noi/x')
        store(fake).check()


if __name__ == '__main__':
    unittest.main()
