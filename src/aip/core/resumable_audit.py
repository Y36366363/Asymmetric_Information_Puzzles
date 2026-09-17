"""Disk-backed, bounded complete-tree audit. Partial progress is never a certificate."""

import json
from math import fsum, isfinite
import sqlite3
from time import monotonic


class ResumableTreeAudit:
    """Replay integer action paths; persist compact recall IDs and frontier atomically.

    revision must identify the adapter, rules and initial-game configuration.
    Checkpoints are JSON/SQLite, not executable pickle. One writer per database.
    """

    def __init__(self, game, path, *, revision):
        if not revision:
            raise ValueError("game revision is required")
        self.game = game
        self.connection = sqlite3.connect(path)
        try:
            self.connection.execute("CREATE TABLE IF NOT EXISTS progress (id INTEGER PRIMARY KEY, payload TEXT)")
            self.connection.execute("CREATE TABLE IF NOT EXISTS infos (id INTEGER PRIMARY KEY, player INTEGER, info TEXT, actions TEXT, recall TEXT, UNIQUE(player, info))")
            row = self.connection.execute("SELECT payload FROM progress WHERE id=1").fetchone()
            if row:
                self.progress = json.loads(row[0])
                if self.progress['revision'] != revision:
                    raise ValueError("checkpoint game revision mismatch")
            else:
                self.progress = dict(revision=revision, frontier=[[]], histories=0,
                                     terminal_histories=0, chance_histories=0,
                                     decision_histories=0, maximum_depth=0, failures=[])
                self._save()
                self.connection.commit()
        except Exception:
            self.connection.close()
            raise

    def close(self):
        self.connection.close()

    def _save(self):
        self.connection.execute("INSERT OR REPLACE INTO progress VALUES (1, ?)",
                                (json.dumps(self.progress),))

    def _branches(self, state):
        player = self.game.current_player(state)
        if player is None:
            outcomes = self.game.chance_outcomes(state)
            probs = [p for _, p in outcomes]
            if (not outcomes or len({a for a, _ in outcomes}) != len(outcomes)
                or any(not isfinite(p) or p < 0 for p in probs)
                or abs(fsum(probs)-1) > 1e-9):
                raise ValueError('invalid_chance_distribution')
            return player, tuple(a for a, _ in outcomes)
        if player not in (0, 1):
            raise ValueError('invalid_current_player')
        actions = self.game.legal_actions(state)
        if not actions or len(set(actions)) != len(actions):
            raise ValueError('invalid_legal_actions')
        return player, actions

    def _replay(self, path):
        state = self.game.initial_state()
        recall = [[], []]
        ancestors = []
        for index in path:
            if state in ancestors or self.game.is_terminal(state):
                raise ValueError('invalid_or_cyclic_checkpoint_path')
            ancestors.append(state)
            player, actions = self._branches(state)
            if not 0 <= index < len(actions):
                raise ValueError('invalid_checkpoint_action_index')
            if player is not None:
                info = repr(self.game.information_set(state))
                row = self.connection.execute("SELECT id FROM infos WHERE player=? AND info=?",
                                              (player, info)).fetchone()
                if row is None:
                    raise ValueError('checkpoint_ancestor_information_set_missing')
                recall[player].append([row[0], index])
            state = self.game.next_state(state, actions[index])
        if state in ancestors:
            raise ValueError('cyclic_game_graph')
        return state, recall

    def advance(self, *, maximum_histories=10_000, maximum_seconds=30.0):
        if maximum_histories <= 0 or not isfinite(maximum_seconds) or maximum_seconds <= 0:
            raise ValueError('chunk budgets must be positive and finite')
        # Restore in-memory progress if any operation fails before commit.
        original = json.dumps(self.progress)
        started = monotonic()
        processed = 0
        try:
            with self.connection:
                while (self.progress['frontier'] and not self.progress['failures']
                       and processed < maximum_histories
                       and monotonic()-started < maximum_seconds):
                    path = self.progress['frontier'].pop()
                    try:
                        state, recall = self._replay(path)
                        if self.game.is_terminal(state):
                            if not isfinite(self.game.utility_player_zero(state)):
                                raise ValueError('nonfinite_terminal_utility')
                            self.progress['terminal_histories'] += 1
                        else:
                            player, actions = self._branches(state)
                            if player is None:
                                self.progress['chance_histories'] += 1
                            else:
                                self.progress['decision_histories'] += 1
                                info = repr(self.game.information_set(state))
                                serialized_actions = json.dumps([repr(a) for a in actions])
                                serialized_recall = json.dumps(recall[player])
                                row = self.connection.execute("SELECT actions, recall FROM infos WHERE player=? AND info=?",
                                                              (player, info)).fetchone()
                                if row is None:
                                    self.connection.execute("INSERT INTO infos(player,info,actions,recall) VALUES (?,?,?,?)",
                                                            (player, info, serialized_actions, serialized_recall))
                                elif row[0] != serialized_actions:
                                    raise ValueError('inconsistent_information_set_actions')
                                elif row[1] != serialized_recall:
                                    raise ValueError('imperfect_recall')
                            self.progress['frontier'].extend(path+[i] for i in reversed(range(len(actions))))
                    except ValueError as error:
                        self.progress['failures'].append(str(error))
                    self.progress['histories'] += 1
                    self.progress['maximum_depth'] = max(self.progress['maximum_depth'], len(path))
                    processed += 1
                self._save()
        except Exception:
            self.progress = json.loads(original)
            raise
        return self.report()

    def report(self):
        complete = not self.progress['frontier'] and not self.progress['failures']
        return {k: v for k, v in self.progress.items() if k != 'frontier'} | {
            'frontier_nodes': len(self.progress['frontier']),
            'information_sets': self.connection.execute('SELECT COUNT(*) FROM infos').fetchone()[0],
            'complete': complete,
            'structural_audit_passed': complete,
            'equilibrium_certified': False,
            'status': 'failed' if self.progress['failures'] else ('complete' if complete else 'paused'),
        }
