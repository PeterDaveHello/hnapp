import unittest
from datetime import datetime, timezone
from unittest import mock

import hnapp
from models.item import Item


class ItemJsonEntryTests(unittest.TestCase):

    def test_json_entry_formats_dates_with_http_date(self):
        date_posted = datetime(2024, 1, 2, 11, 4, 5, tzinfo=timezone.utc)
        date_updated = datetime(2024, 1, 3, 12, 30, 0)
        item = Item(
            id=123,
            kind='story',
            subkind='link',
            date_posted=date_posted,
            date_updated=date_updated
        )

        with mock.patch('models.item.http_date', side_effect=[
            'Tue, 02 Jan 2024 11:04:05 GMT',
            'Wed, 03 Jan 2024 12:30:00 GMT'
        ]) as mocked_http_date:
            entry = item.json_entry()

        self.assertEqual(entry['date_posted'], 'Tue, 02 Jan 2024 11:04:05 GMT')
        self.assertEqual(entry['date_updated'], 'Wed, 03 Jan 2024 12:30:00 GMT')
        self.assertEqual(mocked_http_date.call_count, 2)


if __name__ == '__main__':
    unittest.main()
