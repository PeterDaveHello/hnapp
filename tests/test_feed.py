import unittest
import xml.etree.ElementTree as ET

from hnapp import AtomFeed


def extract_id(xml_bytes: bytes) -> str:
    root = ET.fromstring(xml_bytes)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    return root.find('atom:id', ns).text


class AtomFeedTests(unittest.TestCase):

    def test_feed_id_uses_feed_url(self):
        feed = AtomFeed(title='Test', feed_url='https://example.com/rss', url='https://example.com')
        feed.add(title='Entry', id='https://example.com/x')
        data = feed.get_response().get_data()
        self.assertEqual(extract_id(data), 'https://example.com/rss')

    def test_feed_id_fallback(self):
        feed = AtomFeed(title='Fallback Feed')
        data = feed.get_response().get_data()
        feed_id = extract_id(data)
        self.assertTrue(feed_id.startswith('urn:uuid:'))

if __name__ == '__main__':
    unittest.main()
