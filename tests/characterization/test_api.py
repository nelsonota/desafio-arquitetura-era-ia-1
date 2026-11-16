import json
import os
import unittest
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get('HELPDESK_URL', 'http://localhost:8000').rstrip('/')
TICKET = {'ticket_id': 'TK-00042', 'text': 'Meu pedido #481516 não chegou e já passou do prazo, urgente'}


def post(path, data):
    request = urllib.request.Request(BASE + path, json.dumps(data).encode('utf-8'), {'Content-Type': 'application/json'})
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, json.load(response)


class Characterization(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(post('/tickets/classification', TICKET), (200, {'ticket_id': 'TK-00042', 'category': 'delivery', 'priority': 'high'}))

    def test_suggestion(self):
        expected = json.loads((Path(__file__).parent / 'suggestion.json').read_text(encoding='utf-8'))
        self.assertEqual(post('/tickets/reply-suggestion', TICKET), (200, expected))

    def test_extraction(self):
        self.assertEqual(post('/tickets/extraction', TICKET), (200, {'ticket_id': 'TK-00042', 'order_number': '#481516', 'product': None}))

    def test_report_with_tickets(self):
        expected = json.loads((Path(__file__).parent / 'topics.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(post('/reports/topics', {'start': '2026-08-01', 'end': '2026-08-01'}), (200, expected))

    def test_report_empty_period(self):
        self.assertEqual(post('/reports/topics', {'start': '2025-01-01', 'end': '2025-01-01'}), (200, {'start': '2025-01-01', 'end': '2025-01-01', 'total_tickets': 0, 'topics': []}))

    def test_invalid_ticket_inputs(self):
        expected = {'detail': [{'type': 'string_too_short', 'loc': ['body', 'text'], 'msg': 'String should have at least 1 character', 'input': '', 'ctx': {'min_length': 1}}]}
        for path in ('/tickets/classification', '/tickets/reply-suggestion', '/tickets/extraction'):
            with self.subTest(path=path):
                self.assertEqual(post(path, {'ticket_id': 'TK-1', 'text': ''}), (422, expected))

    def test_invalid_period(self):
        self.assertEqual(post('/reports/topics', {'start': '2026-08-02', 'end': '2026-08-01'}), (422, {'detail': 'A data inicial é posterior à data final'}))


if __name__ == '__main__':
    unittest.main()
