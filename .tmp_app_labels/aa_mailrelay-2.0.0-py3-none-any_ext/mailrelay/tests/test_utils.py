from django.test import TestCase

from mailrelay.utils import chunks_by_lines


class TestChunkLines(TestCase):
    def test_should_produce_chunks(self):
        # given
        input = "abcdef\nghijklmnopq\nrstuvwxyz"
        # when
        result = chunks_by_lines(input, 20)
        # then
        self.assertListEqual(result, ["abcdef\nghijklmnopq\n", "rstuvwxyz"])
