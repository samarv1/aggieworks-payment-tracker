"""Synthetic Gmail fixtures; tests never connect to a real mailbox."""
import base64
from datetime import datetime, timezone
import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper import VenmoEmailScraper, scrape_emails
from errors import ScraperError


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

    def test_empty_keyword_tokens_do_not_match_everything(self):
        for keywords in ['dues,', ', dues', 'dues,, retreat, ']:
            with self.subTest(keywords=keywords):
                self.assertFalse(self.scraper._matches_category({'note': 'dinner'}, 'other', keywords))
                self.assertTrue(self.scraper._matches_category({'note': 'DUES'}, 'other', keywords))
        for keywords in [None, '', ' ', ', ,']:
            self.assertTrue(self.scraper._matches_category({'note': 'dinner'}, 'other', keywords))

    def test_zelle_missing_memo_does_not_borrow_next_payment(self):
        for memo in ['', 'Memo:\n']:
            payments = self.scraper._extract_zelle_payments(message(
                'Zelle payment received',
                'TAYLOR EXAMPLE sent you $25.00\n' + memo
                + 'JORDAN SAMPLE sent you $30.00\nMemo: dues',
            ))
            self.assertEqual([p['note'] for p in payments], ['', 'dues'])

    def test_zelle_uppercase_memo_stays_out_of_next_name(self):
        payments = self.scraper._extract_zelle_payments(message(
            'Zelle payment received',
            'TAYLOR EXAMPLE sent you $25.00\nMemo: RETREAT\n'
            'JORDAN SAMPLE sent you $30.00\nMemo: DUES',
        ))
        self.assertEqual([p['person'] for p in payments], ['TAYLOR EXAMPLE', 'JORDAN SAMPLE'])
        self.assertEqual([p['note'] for p in payments], ['RETREAT', 'DUES'])

    def test_payment_amounts_accept_sentence_punctuation(self):
        for suffix in ['.', ', thanks', '. Thank you', '!']:
            with self.subTest(suffix=suffix):
                incoming = self.scraper._extract_venmo_payment(message(
                    f'Taylor Example paid you $25.00{suffix}', 'dues See transaction',
                ))
                outgoing = self.scraper._extract_venmo_payment(message(
                    f'You paid Taylor Example $25.00{suffix}', 'dues See transaction',
                ))
                zelle = self.scraper._extract_zelle_payments(message(
                    'Zelle payment received', f'TAYLOR EXAMPLE sent you $25.00{suffix}\nMemo: dues',
                ))
                self.assertIsNotNone(incoming)
                self.assertIsNotNone(outgoing)
                self.assertEqual(incoming['amount'], 25.0)
                self.assertEqual(outgoing['amount'], 25.0)
                self.assertEqual(len(zelle), 1)
                self.assertEqual(zelle[0]['amount'], 25.0)

    def test_wrapped_zelle_names_do_not_absorb_previous_memo(self):
        for mime_type, body in [
            ('text/plain', 'TAYLOR\nEXAMPLE sent you $25.00\nMemo: RETREAT\n'
             'JORDAN\nSAMPLE sent you $30.00\nMemo: DUES'),
            ('text/plain', 'TAYLOR\r\nEXAMPLE sent you $25.00\r\nMemo:\r\nRETREAT\r\n'
             'JORDAN\r\nSAMPLE sent you $30.00\r\nMemo: DUES'),
            ('text/html', '<div>TAYLOR<br>EXAMPLE sent you $25.00</div><div>Memo: RETREAT</div>'
             '<div>JORDAN<br>SAMPLE sent you $30.00</div><div>Memo: DUES</div>'),
        ]:
            with self.subTest(mime_type=mime_type, body=body):
                sample = message('Zelle payment received', body)
                sample['payload']['mimeType'] = mime_type
                payments = self.scraper._extract_zelle_payments(sample)
                self.assertEqual([p['person'] for p in payments], ['TAYLOR EXAMPLE', 'JORDAN SAMPLE'])
                self.assertEqual([p['note'] for p in payments], ['RETREAT', 'DUES'])
                self.assertEqual([p['payment_index'] for p in payments], [0, 1])

    def test_next_line_zelle_memos_survive_category_filtering(self):
        for mime_type, body in [
            ('text/plain', 'TAYLOR EXAMPLE sent you $25.00\nMemo:\ndues'),
            ('text/plain', 'TAYLOR EXAMPLE sent you $25.00\r\nMessage:\r\ndues'),
            ('text/html', '<div>TAYLOR EXAMPLE sent you $25.00</div><div>Note:</div><div>dues</div>'),
        ]:
            with self.subTest(mime_type=mime_type):
                sample = message('Zelle payment received', body)
                sample['payload']['mimeType'] = mime_type
                self.scraper.service = Mock()
                self.scraper._get_messages = Mock(return_value=[sample])
                payments = self.scraper.search_payment_emails(datetime(2026, 10, 19), 'dues', source='zelle')
                self.assertEqual(len(payments), 1)
                self.assertEqual(payments[0]['note'], 'dues')

    def test_venmo_notes_preserve_punctuation_and_exclude_amount(self):
        for note in ['Fall retreat', "Dinner, snacks & Sam’s ticket! 🎉", '']:
            with self.subTest(note=note):
                payment = self.scraper._extract_venmo_payment(message(
                    'Taylor Example paid you $25.00',
                    f'Taylor Example paid you $25.00 {note} See transaction',
                ))
                self.assertEqual(payment['note'], note)
        self.assertEqual(self.scraper._extract_payment_note('Note: Snacks. Thanks!\nFooter'), 'Snacks. Thanks!')
        self.assertIsNone(self.scraper._extract_payment_note('No payment note'))

    def test_amounts_with_thousands_separators(self):
        for amount in ['1,000.00', '12,345,678.90', '1000.00']:
            expected = float(amount.replace(',', ''))
            venmo = self.scraper._extract_venmo_payment(message(
                f'Taylor Example paid you ${amount}', f'${amount} Retreat See transaction',
            ))
            zelle = self.scraper._extract_zelle_payments(message(
                'Zelle payment received', f'TAYLOR EXAMPLE sent you ${amount}\nMemo: retreat',
            ))
            self.assertEqual(venmo['amount'], expected)
            self.assertEqual(zelle[0]['amount'], expected)

    def test_malformed_amounts_are_not_partially_matched(self):
        for amount in ['1,00.00', '1234,567.89', '25.000', '25.00,123', '25.00.00']:
            with self.subTest(amount=amount):
                self.assertIsNone(self.scraper._extract_venmo_payment(message(
                    f'Taylor Example paid you ${amount}', 'dues See transaction',
                )))
                self.assertEqual(self.scraper._extract_zelle_payments(message(
                    'Zelle payment received', f'TAYLOR EXAMPLE sent you ${amount}',
                )), [])

    def test_html_bodies_at_each_nesting_level(self):
        html = ('<div><span>TAYLOR</span> <span>EXAMPLE</span></div>'
                '<div>sent you $25.00</div><div>Memo: <b>retreat</b></div>'
                '<div>JORDAN SAMPLE sent you $30.00</div><div>Memo: dues</div>')
        original = message('Zelle payment received', html)
        original['payload']['mimeType'] = 'text/html'
        for depth in range(3):
            sample = message('Zelle payment received', '')
            body = original['payload']
            for _ in range(depth):
                body = {'mimeType': 'multipart/mixed', 'parts': [body]}
            sample['payload'].update(body)
            payments = self.scraper._extract_zelle_payments(sample)
            self.assertEqual([p['person'] for p in payments], ['TAYLOR EXAMPLE', 'JORDAN SAMPLE'])
            self.assertEqual([p['note'] for p in payments], ['retreat', 'dues'])

    def test_alternatives_prefer_plain_text_and_skip_attachments(self):
        plain = message('', 'correct body')['payload']
        plain['mimeType'] = 'text/plain'
        html = message('', '<p>HTML body</p>')['payload']
        html['mimeType'] = 'text/html'
        attachment = dict(plain, filename='payment.txt')
        alternative = {'mimeType': 'multipart/alternative', 'parts': [html, plain]}
        payload = {'mimeType': 'multipart/mixed', 'parts': [attachment, alternative]}
        self.assertEqual(self.scraper._get_email_body(payload), 'correct body')
        plain['body']['data'] = ''
        self.assertEqual(self.scraper._get_email_body(payload).strip(), 'HTML body')
        self.assertEqual(self.scraper._get_email_body(dict(attachment, filename='', headers=[
            {'name': 'Content-Disposition', 'value': 'attachment'}
        ])), '')

    def test_authorization_errors_are_classified_without_raw_details(self):
        with patch.object(VenmoEmailScraper, 'authenticate', side_effect=RuntimeError('private-token')):
            with self.assertRaises(ScraperError) as result:
                scrape_emails('test@example.com', datetime.now(), 'dues')
            self.assertEqual(result.exception.code, 'authorization_failed')
            self.assertNotIn('private-token', str(result.exception))
        for code in ['account_mismatch', 'oauth_setup_required']:
            with patch.object(VenmoEmailScraper, 'authenticate', side_effect=ScraperError(code)):
                with self.assertRaises(ScraperError) as result:
                    scrape_emails('test@example.com', datetime.now(), 'dues')
                self.assertEqual(result.exception.code, code)

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
