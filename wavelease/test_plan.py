import unittest

from wavelease.plan import Lease, edges, waves


class Waves(unittest.TestCase):
    def test_consumer_waits_for_producer_even_with_disjoint_files(self):
        producer = Lease("P", {"a.py"}, set(), {"a.f"})
        consumer = Lease("C", {"new.py"}, {"a.f"})
        other = Lease("O", {"b.py"}, set())
        self.assertEqual(edges([producer, consumer, other]), [("P", "C", ["a.f"])])
        self.assertEqual(waves([consumer, producer, other]), [["P", "O"], ["C"]])

    def test_overlapping_writes_never_share_a_wave(self):
        self.assertEqual(waves([Lease("A", {"x.py"}, set()), Lease("B", {"x.py"}, set())]), [["A"], ["B"]])


if __name__ == "__main__":
    unittest.main()
