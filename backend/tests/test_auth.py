import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scraper
from errors import ScraperError


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        location = patch.object(scraper, '__file__', str(self.root / 'scraper.py'))
        location.start()
        self.addCleanup(location.stop)
        network = patch('requests.sessions.Session.request', side_effect=AssertionError('Unexpected network request'))
        network.start()
        self.addCleanup(network.stop)
        self.config = {'installed': {
            'client_id': 'synthetic-client', 'client_secret': 'synthetic-secret',
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': ['http://localhost'],
        }}
        self.credentials = Credentials(
            token='synthetic-access-token', refresh_token='synthetic-refresh-token',
            token_uri=self.config['installed']['token_uri'], client_id='synthetic-client',
            client_secret='synthetic-secret', scopes=scraper.SCOPES,
            expiry=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
        )
        self.service = Mock()
        self.service.users.return_value.getProfile.return_value.execute.return_value = {
            'emailAddress': 'test@example.com'
        }

    def test_missing_oauth_config_has_specific_error(self):
        with self.assertRaises(ScraperError) as result:
            scraper.VenmoEmailScraper('test@example.com').authenticate()
        self.assertEqual(result.exception.code, 'oauth_setup_required')

    def test_authorize_and_reuse_cached_credentials(self):
        (self.root / 'credentials.json').write_text(json.dumps(self.config))
        with patch.object(InstalledAppFlow, 'run_local_server', return_value=self.credentials) as authorize, \
                patch('googleapiclient.discovery.build', return_value=self.service):
            account = scraper.VenmoEmailScraper('test@example.com')
            self.assertTrue(account.authenticate())
            self.assertTrue(scraper.VenmoEmailScraper('test@example.com').authenticate())
            authorize.assert_called_once_with(port=0, login_hint='test@example.com', prompt='select_account')
        token_files = list((self.root / 'tokens').glob('*.json'))
        self.assertEqual(len(token_files), 1)
        self.assertEqual(token_files[0].stat().st_mode & 0o777, 0o600)

    def test_account_mismatch_does_not_persist_token(self):
        (self.root / 'credentials.json').write_text(json.dumps(self.config))
        self.service.users.return_value.getProfile.return_value.execute.return_value = {
            'emailAddress': 'other@example.com'
        }
        with patch.object(InstalledAppFlow, 'run_local_server', return_value=self.credentials), \
                patch('googleapiclient.discovery.build', return_value=self.service):
            with self.assertRaises(ScraperError) as result:
                scraper.VenmoEmailScraper('test@example.com').authenticate()
        self.assertEqual(result.exception.code, 'account_mismatch')
        self.assertEqual(list((self.root / 'tokens').glob('*.json')), [])

    def test_expired_credentials_refresh_without_browser(self):
        (self.root / 'credentials.json').write_text(json.dumps(self.config))
        with patch.object(InstalledAppFlow, 'run_local_server', return_value=self.credentials), \
                patch('googleapiclient.discovery.build', return_value=self.service):
            scraper.VenmoEmailScraper('test@example.com').authenticate()
        token_file = next((self.root / 'tokens').glob('*.json'))
        token = json.loads(token_file.read_text())
        token['expiry'] = '2000-01-01T00:00:00Z'
        token_file.write_text(json.dumps(token))
        response = Mock(status=200, data=json.dumps({
            'access_token': 'synthetic-refreshed-token', 'expires_in': 3600,
            'token_type': 'Bearer',
        }).encode())
        with patch('google.auth.transport.requests.Request.__call__', return_value=response) as refresh, \
                patch.object(InstalledAppFlow, 'run_local_server') as authorize, \
                patch('googleapiclient.discovery.build', return_value=self.service):
            self.assertTrue(scraper.VenmoEmailScraper('test@example.com').authenticate())
            refresh.assert_called_once()
            authorize.assert_not_called()
        self.assertEqual(json.loads(token_file.read_text())['token'], 'synthetic-refreshed-token')

    def test_oauth_client_builds_readonly_authorization_url(self):
        flow = InstalledAppFlow.from_client_config(self.config, scraper.SCOPES)
        url, state = flow.authorization_url(login_hint='test@example.com')
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query['scope'], scraper.SCOPES)
        self.assertEqual(query['response_type'], ['code'])
        self.assertEqual(query['login_hint'], ['test@example.com'])
        self.assertEqual(query['state'], [state])


if __name__ == '__main__':
    unittest.main()
