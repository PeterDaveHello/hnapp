import sys
import types
import unittest
from unittest import mock

import requests

if 'bleach' not in sys.modules:
    bleach_stub = types.ModuleType('bleach')

    def _clean_stub(html, **kwargs):
        return html

    bleach_stub.clean = _clean_stub
    sys.modules['bleach'] = bleach_stub

from scraper import Scraper
from models.lost_item import LostItem


class ScraperRequestTests(unittest.TestCase):
    def setUp(self):
        self.scraper = Scraper()

    def test_fetch_item_returns_payload(self):
        with mock.patch.object(self.scraper, '_request_json', return_value={'id': 1, 'type': 'story'}) as mocked:
            result = self.scraper.fetch_item(1)
        mocked.assert_called_once_with('item/1')
        self.assertEqual(result['id'], 1)
        self.assertEqual(result['type'], 'story')

    def test_fetch_item_null_returns_lost_item(self):
        with mock.patch.object(self.scraper, '_request_json', return_value=None):
            result = self.scraper.fetch_item(42)
        self.assertIsInstance(result, LostItem)
        self.assertEqual(result.id, 42)
        self.assertEqual(result.reason, 'null')

    def test_fetch_item_non_transient_http_error_records_details(self):
        response = requests.Response()
        response.status_code = 404
        response._content = b'not found'
        http_error = requests.exceptions.HTTPError(response=response)
        with mock.patch.object(self.scraper, '_request_json', side_effect=http_error):
            with mock.patch('scraper.db.session.get', return_value=None):
                result = self.scraper.fetch_item(99)
        self.assertIsInstance(result, LostItem)
        self.assertEqual(result.id, 99)
        self.assertEqual(result.reason, 'HTTP/404')
        self.assertIn('not found', result.response)

    def test_fetch_item_transient_http_error_raises(self):
        response = requests.Response()
        response.status_code = 500
        response._content = b'internal error'
        http_error = requests.exceptions.HTTPError(response=response)
        with mock.patch.object(self.scraper, '_request_json', side_effect=http_error):
            with mock.patch('scraper.db.session.get') as get_lost_item:
                with self.assertRaises(requests.exceptions.HTTPError):
                    self.scraper.fetch_item(99)
        get_lost_item.assert_not_called()

    def test_fetch_item_network_error_raises(self):
        network_error = requests.exceptions.RequestException("timeout")
        with mock.patch.object(self.scraper, '_request_json', side_effect=network_error):
            with self.assertRaises(requests.exceptions.RequestException):
                self.scraper.fetch_item(77)

    def test_save_newest_items_stops_on_network_error(self):
        network_error = requests.exceptions.RequestException("timeout")
        with mock.patch.object(self.scraper, 'fetch_max_item_id', return_value=7):
            with mock.patch('scraper.Status.get_max_item_id', return_value=4):
                with mock.patch.object(self.scraper, 'fetch_item', side_effect=[{'id': 5, 'type': 'story'}, network_error]):
                    with mock.patch('scraper.Status.set_max_item_id') as set_max_item_id:
                        with mock.patch('scraper.Item.create_or_update'):
                            with mock.patch('scraper.db.session.add'):
                                with mock.patch('scraper.db.session.commit'):
                                    with self.assertRaises(requests.exceptions.RequestException):
                                        self.scraper.save_newest_items()
        set_max_item_id.assert_called_once_with(5)

    def test_save_newest_items_stops_on_transient_http_error(self):
        response = requests.Response()
        response.status_code = 503
        response._content = b'upstream down'
        http_error = requests.exceptions.HTTPError(response=response)
        with mock.patch.object(self.scraper, 'fetch_max_item_id', return_value=7):
            with mock.patch('scraper.Status.get_max_item_id', return_value=4):
                with mock.patch.object(self.scraper, 'fetch_item', side_effect=[{'id': 5, 'type': 'story'}, http_error]):
                    with mock.patch('scraper.Status.set_max_item_id') as set_max_item_id:
                        with mock.patch('scraper.Item.create_or_update'):
                            with mock.patch('scraper.db.session.add'):
                                with mock.patch('scraper.db.session.commit'):
                                    with self.assertRaises(requests.exceptions.HTTPError):
                                        self.scraper.save_newest_items()
        set_max_item_id.assert_called_once_with(5)

    def test_fetch_top_story_ids_uses_request_helper(self):
        with mock.patch.object(self.scraper, '_request_json', return_value=[1, 2, 3]) as mocked:
            result = self.scraper.fetch_top_story_ids()
        mocked.assert_called_once_with('topstories')
        self.assertEqual(result, [1, 2, 3])


if __name__ == '__main__':
    unittest.main()
