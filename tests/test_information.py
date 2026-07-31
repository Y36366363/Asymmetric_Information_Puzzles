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


if __name__ == "__main__":
    unittest.main()
