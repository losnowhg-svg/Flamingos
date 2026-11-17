"""3.22: two friends saving at the same time: the work is joined, nobody covers the other."""
import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))

import shared_store as ss
from fake_github import FakeGitHub


def store(fake):
    return ss.GitHubStore('buono', fake.repo, transport=fake)


BASE = {'season_scorers': [{'name': 'TEU', 'goals': 1}],
        'season_ledger': {'2026-11-05|CASTEUNITED': {'goals': {'TEU': 1}}},
        'studio_models': {'Full Time': {'home_score': 2, 'title': 'FULL TIME'}, 'Classifica': {'prev_pos': 0}},
        'shared_note': ''}


def snap(state, author, page='Settimana'):
    return dict(ss.snapshot({}, page, author), state=dict(state))


class Join(unittest.TestCase):
    def test_who_changed_wins(self):
        mine = dict(BASE, shared_note='Pagelle fatte')
        theirs = dict(BASE, season_scorers=[{'name': 'TEU', 'goals': 7}])
        joined = ss.merge_state(BASE, mine, theirs)
        self.assertEqual(joined['shared_note'], 'Pagelle fatte')
        self.assertEqual(joined['season_scorers'], [{'name': 'TEU', 'goals': 7}])

    def test_inside_the_graphics_and_the_season(self):
        mine = dict(BASE, studio_models={'Full Time': {'home_score': 3, 'title': 'FULL TIME'}, 'Classifica': {'prev_pos': 0}})
        theirs = dict(BASE, studio_models={'Full Time': {'home_score': 2, 'title': 'VITTORIA'}, 'Classifica': {'prev_pos': 9}},
                      season_ledger=dict(BASE['season_ledger'], **{'2026-11-14|LIONS25': {'goals': {'TEU': 1}}}))
        joined = ss.merge_state(BASE, mine, theirs)
        self.assertEqual(joined['studio_models'], {'Full Time': {'home_score': 3, 'title': 'VITTORIA'}, 'Classifica': {'prev_pos': 9}})
        self.assertEqual(sorted(joined['season_ledger']), ['2026-11-05|CASTEUNITED', '2026-11-14|LIONS25'])

    def test_same_thing_changed_by_both_this_save_wins(self):
        mine = dict(BASE, shared_note='mia')
        theirs = dict(BASE, shared_note='sua')
        self.assertEqual(ss.merge_state(BASE, mine, theirs)['shared_note'], 'mia')

    def test_added_and_removed_keys(self):
        theirs = dict(BASE, csi_sync={'ok_at': 'ora'})
        mine = {k: v for k, v in BASE.items() if k != 'shared_note'}
        joined = ss.merge_state(BASE, mine, theirs)
        self.assertEqual(joined['csi_sync'], {'ok_at': 'ora'})
        self.assertNotIn('shared_note', joined)                       # removed by me, untouched by them

    def test_unknown_keys_never_travel(self):
        self.assertNotIn('vault', ss.merge_state({}, {'vault': 1}, {}))


class Store(unittest.TestCase):
    def test_two_friends_at_once_both_kept(self):
        fake = FakeGitHub()
        sha0, _ = store(fake).save(snap(BASE, 'LUCA'))
        # Marco (or Claude) saves the scorers on top
        store(fake).save(snap(dict(BASE, season_scorers=[{'name': 'TEU', 'goals': 7}]), 'MARCO'), sha0)
        # Lorenzo's app still has the old sha and only changed the note
        mine = snap(dict(BASE, shared_note='Matchday pronto'), 'LORENZO')
        _, theirs = store(fake).save(mine, sha0, base=BASE)
        self.assertEqual(theirs['author'], 'MARCO')
        saved, _ = store(fake).load()
        self.assertEqual(saved['state']['season_scorers'], [{'name': 'TEU', 'goals': 7}])    # Marco's work stays
        self.assertEqual(saved['state']['shared_note'], 'Matchday pronto')                    # and Lorenzo's too
        self.assertEqual(fake.commits[-1][1], 'Lavoro unito di LORENZO (Settimana)')

    def test_going_back_still_covers(self):
        fake = FakeGitHub()
        sha0, _ = store(fake).save(snap(BASE, 'LUCA'))
        store(fake).save(snap(dict(BASE, shared_note='nuova'), 'MARCO'), sha0)
        store(fake).save(snap(BASE, 'LORENZO'), sha0, base=None)
        self.assertEqual(store(fake).load()[0]['state']['shared_note'], '')


class Saver(unittest.TestCase):
    def test_the_friends_part_comes_back_to_this_session(self):
        fake = FakeGitHub()
        sha0, _ = store(fake).save(snap(BASE, 'LUCA'))
        store(fake).save(snap(dict(BASE, season_scorers=[{'name': 'TEU', 'goals': 7}]), 'MARCO'), sha0)
        meta = {'sha': sha0, 'base': dict(BASE)}
        saver = ss.Saver(meta, throttle=0)
        saver.submit(lambda: store(fake), snap(dict(BASE, shared_note='ok'), 'LORENZO'))
        self.assertTrue(saver.wait())
        self.assertIsNone(meta.get('error'))
        self.assertEqual(meta['incoming'], {'season_scorers': ([{'name': 'TEU', 'goals': 1}], [{'name': 'TEU', 'goals': 7}])})
        self.assertEqual(meta['merged']['author'], 'MARCO')
        self.assertEqual(meta['base']['season_scorers'], [{'name': 'TEU', 'goals': 7}])     # the next join starts here
        self.assertNotIn('overwrote', meta)
        # the next save, with nothing new from anyone, is a plain save
        saver.submit(lambda: store(fake), snap(dict(meta['base'], shared_note='ok, fatto'), 'LORENZO'))
        self.assertTrue(saver.wait())
        self.assertEqual(store(fake).load()[0]['state']['season_scorers'], [{'name': 'TEU', 'goals': 7}])


if __name__ == '__main__':
    unittest.main()
