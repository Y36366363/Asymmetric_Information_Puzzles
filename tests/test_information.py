import unittest

from aip.core.information import InformationSet, Observation


class InformationSetTests(unittest.TestCase):
    def test_public_observation_filters_states_and_enters_public_history(self) -> None:
        info = InformationSet("hats-0", "A", ("red", "blue"))
        updated = info.update(
            Observation("announcement", "not-blue", is_public=True, timestamp=1),
            lambda state, observation: state != "blue",
        )
        self.assertEqual(updated.possible_states, ("red",))
        self.assertEqual(len(updated.public_history), 1)

    def test_beliefs_must_sum_to_one(self) -> None:
        with self.assertRaises(ValueError):
            InformationSet("bad", "A", (1, 2), beliefs={1: 0.2, 2: 0.2})

    def test_bayesian_update_normalizes_and_records_public_fact(self) -> None:
        information = InformationSet(
            key="coin",
            player_id=0,
            possible_states=("fair", "biased"),
            beliefs={"fair": 0.5, "biased": 0.5},
        )
        posterior = information.bayesian_update(
            Observation("heads", True, is_public=True),
            lambda state, _observation: 0.5 if state == "fair" else 0.9,
        )
        self.assertAlmostEqual(posterior.beliefs["biased"], 0.9 / 1.4)
        self.assertEqual(len(posterior.public_history), 1)


if __name__ == "__main__":
    unittest.main()
