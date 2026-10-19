import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from errors import ERROR_MESSAGES, ScraperError


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.config = dict(email='test@example.com', startDate='2026-10-19',
                           startTime='00:00', category='dues', source='venmo')

    def request(self, **changes):
        return self.client.post('/api/scraper/run', json=dict(self.config, **changes))

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.json(), {'detail': {'code': code, 'message': ERROR_MESSAGES[code]}})

    def test_validation_errors_are_structured(self):
        self.assert_error(self.request(category='unknown'), 422, 'invalid_request')
        self.assert_error(self.request(startDate='bad-date'), 400, 'invalid_datetime')
        self.assertFalse(main._scrape_lock.locked())

    def test_conflict_preserves_active_search_lock(self):
        main._scrape_lock.acquire()
        try:
            self.assert_error(self.request(), 409, 'search_running')
            self.assertTrue(main._scrape_lock.locked())
        finally:
            main._scrape_lock.release()

    def test_known_errors_and_lock_release(self):
        for code, status in [('invalid_email', 400), ('account_mismatch', 400),
                             ('oauth_setup_required', 503), ('authorization_failed', 503)]:
            with patch.object(main, 'scrape_emails', side_effect=ScraperError(code)), \
                    patch.object(main, 'save_payments_to_csv') as save:
                self.assert_error(self.request(), status, code)
                save.assert_not_called()
                self.assertFalse(main._scrape_lock.locked())

    def test_unexpected_errors_do_not_disclose_exception_details(self):
        with patch.object(main, 'scrape_emails', side_effect=RuntimeError('private-token')):
            response = self.request()
        self.assert_error(response, 500, 'search_failed')
        self.assertNotIn('private-token', response.text)
        self.assertFalse(main._scrape_lock.locked())

    def test_export_failure_releases_lock(self):
        with patch.object(main, 'scrape_emails', return_value=[]), \
                patch.object(main, 'save_payments_to_csv', side_effect=OSError('private-path')):
            self.assert_error(self.request(), 500, 'search_failed')
        self.assertFalse(main._scrape_lock.locked())

    def test_success_preserves_result_contract(self):
        with patch.object(main, 'scrape_emails', return_value=[]), \
                patch.object(main, 'save_payments_to_csv', return_value=('synthetic.csv', 0.0)), \
                patch.object(main, 'get_payment_count', return_value=0):
            response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['new_count'], 0)
        self.assertEqual(response.json()['data']['total_amount'], 0.0)
        self.assertFalse(main._scrape_lock.locked())


if __name__ == '__main__':
    unittest.main()
