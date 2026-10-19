"""Synthetic Gmail fixtures; tests never connect to a real mailbox."""
import base64
from datetime import datetime, timezone
import unittest
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper import VenmoEmailScraper


def message(subject, body, message_id='message-1'):
    return {
        'id': message_id,
        'payload': {
            'headers': [
                {'name': 'Subject', 'value': subject},
                {'name': 'Date', 'value': 'Mon, 19 Oct 2026 12:00:00 +0000'},
            ],
            'body': {'data': base64.urlsafe_b64encode(body.encode()).decode()},
        },
    }


class PaymentParserTests(unittest.TestCase):
    def setUp(self):
        self.scraper = VenmoEmailScraper('test@example.com')

    def test_venmo_incoming_details_and_stable_identity(self):
        payment = self.scraper._extract_venmo_payment(message(
            'Taylor Example paid you $25.00',
            'Fall retreat See transaction\nTransaction ID: 123456789',
        ))
        self.assertEqual(payment['person'], 'Taylor Example')
        self.assertEqual(payment['amount'], 25.0)
        self.assertEqual(payment['type'], 'incoming')
        self.assertEqual(payment['transaction_id'], '123456789')
        self.assertEqual(payment['message_id'], 'message-1')
        self.assertEqual(payment['source'], 'venmo')
        self.assertIn('retreat', payment['note'])
        self.assertEqual(payment['date'], '2026-10-19T12:00:00+00:00')

    def test_search_filters_outgoing_and_unrelated_payments(self):
        self.scraper.service = Mock()
        self.scraper._get_messages = Mock(return_value=[
            message('You paid Taylor Example $25.00', 'retreat See transaction'),
            message('Taylor Example paid you $25.00', 'retreat See transaction'),
            message('Jordan Sample paid you $20.00', 'dues See transaction'),
            message('Your weekly statement', 'No payment'),
        ])
        start = datetime(2026, 10, 19, 10, 30, tzinfo=timezone.utc)
        payments = self.scraper.search_payment_emails(start, 'retreat')
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0]['type'], 'incoming')
        self.scraper._get_messages.assert_called_once_with(
            f'from:venmo@venmo.com after:{int(start.timestamp())}'
        )

    def test_multiple_zelle_payments_keep_independent_identities(self):
        payments = self.scraper._extract_zelle_payments(message(
            'Zelle payment received',
            'TAYLOR EXAMPLE sent you $25.00\nMemo: retreat\n'
            'JORDAN SAMPLE sent you $30.00\nMemo: dues',
        ))
        self.assertEqual([p['person'] for p in payments], ['TAYLOR EXAMPLE', 'JORDAN SAMPLE'])
        self.assertEqual([p['amount'] for p in payments], [25.0, 30.0])
        self.assertEqual([p['note'] for p in payments], ['retreat', 'dues'])
        self.assertEqual([p['payment_index'] for p in payments], [0, 1])
        self.assertTrue(all(p['source'] == 'zelle' and p['message_id'] == 'message-1' for p in payments))

    def test_custom_keywords_are_case_insensitive(self):
        self.assertTrue(self.scraper._matches_category({'note': 'Fall fundraiser'}, 'other', 'donation, FUNDRAISER'))
        self.assertFalse(self.scraper._matches_category({'note': 'dinner'}, 'other', 'donation, fundraiser'))

    def test_message_pagination(self):
        service = Mock()
        self.scraper.service = service
        api = service.users.return_value.messages.return_value
        api.list.return_value.execute.side_effect = [
            {'messages': [{'id': 'one'}], 'nextPageToken': 'next'},
            {'messages': [{'id': 'two'}]},
        ]
        api.get.return_value.execute.side_effect = [{'id': 'one'}, {'id': 'two'}]
        self.assertEqual(self.scraper._get_messages('query'), [{'id': 'one'}, {'id': 'two'}])
        self.assertEqual(api.list.call_args_list[1].kwargs['pageToken'], 'next')

    def test_fetch_failure_is_not_reported_as_empty_results(self):
        self.scraper.service = Mock()
        self.scraper.service.users.return_value.messages.return_value.list.side_effect = RuntimeError('API unavailable')
        with self.assertRaisesRegex(RuntimeError, 'API unavailable'):
            self.scraper._get_messages('query')

    def test_account_normalization_and_rejects_path_input(self):
        self.assertEqual(VenmoEmailScraper(' Test@Example.com ').email, 'test@example.com')
        for invalid in ['../test@example.com', 'test', 'a\\b@example.com']:
            with self.assertRaises(ValueError):
                VenmoEmailScraper(invalid)


if __name__ == '__main__':
    unittest.main()
