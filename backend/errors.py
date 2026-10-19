ERROR_MESSAGES = {
    'invalid_email': 'Enter a valid email address for the Google account you want to use.',
    'invalid_datetime': 'Choose a valid start date and time.',
    'account_mismatch': 'The Google account you authorized does not match the selected email. Run the scraper again and choose the matching account.',
    'oauth_setup_required': 'Gmail setup is incomplete. Add your OAuth client file at backend/credentials.json, then try again.',
    'authorization_failed': 'Could not authorize Gmail access. Run the scraper again and complete Google authorization.',
    'search_running': 'A payment search is already running. Wait for it to finish, then try again.',
    'invalid_request': 'Some search settings are invalid. Check the account, date, time, category, and payment sources.',
    'search_failed': 'The search could not finish. Check the backend terminal for details, then try again.',
}


class ScraperError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(ERROR_MESSAGES[code])


def error_detail(code: str) -> dict:
    return {'code': code, 'message': ERROR_MESSAGES[code]}
