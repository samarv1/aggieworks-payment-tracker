"""
Gmail scraper for Venmo payment emails
"""
import re
from datetime import datetime
from typing import List, Dict, Optional
import base64
from email.utils import parsedate_to_datetime
import os.path
import hashlib
from errors import ScraperError

AMOUNT_PATTERN = r'((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})(?!\d|[,.]\d)'

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Payment sources
PAYMENT_SOURCES = {
    'venmo': 'venmo@venmo.com',
    'zelle': 'alerts@notify.wellsfargo.com'
}

# Category keywords mapping
CATEGORY_KEYWORDS = {
    'retreat': ['retreat', 'retreat payment', 'fall retreat', 'spring retreat', 'annual retreat'],
    'dues': ['dues', 'membership dues', 'club dues', 'quarter dues', 'aggieworks dues'],
}


class VenmoEmailScraper:
    """Scraper for Venmo payment emails from Gmail"""

    def __init__(self, email: str):
        """Select an account; Gmail access is authorized separately with OAuth."""
        self.email = email.strip().lower()
        if not re.fullmatch(r"[^\s@/\\]+@[^\s@/\\]+\.[^\s@/\\]+", self.email):
            raise ScraperError('invalid_email')
        self.service = None

    def authenticate(self):
        """Authorize read-only Gmail access and verify the selected account."""
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        backend_dir = os.path.dirname(os.path.abspath(__file__))
        tokens_dir = os.path.join(backend_dir, 'tokens')
        credentials_file = os.path.join(backend_dir, 'credentials.json')
        os.makedirs(tokens_dir, mode=0o700, exist_ok=True)
        account_key = hashlib.sha256(self.email.encode('utf-8')).hexdigest()
        token_file = os.path.join(tokens_dir, f'token_{account_key}.json')
        creds = None
        # Legacy pickle files are intentionally not deserialized. Reauthorize once.
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_file):
                    raise ScraperError('oauth_setup_required')
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
                creds = flow.run_local_server(
                    port=0, login_hint=self.email, prompt='select_account'
                )

        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()
        if profile.get('emailAddress', '').lower() != self.email:
            raise ScraperError('account_mismatch')
        with open(token_file, 'w', encoding='utf-8', opener=lambda path, flags: os.open(path, flags, 0o600)) as token:
            token.write(creds.to_json())
        self.service = service
        return True

    def search_payment_emails(self, start_datetime: datetime, category: str,
                           custom_keywords: Optional[str] = None, source: str = 'venmo') -> List[Dict]:
        """
        Search for payment emails (Venmo or Zelle) and extract payment information

        Args:
            start_datetime: Start date/time to search from
            category: Category to filter (retreat, dues, or other)
            custom_keywords: Custom keywords if category is 'other'
            source: Payment source ('venmo' or 'zelle')

        Returns:
            List of payment dictionaries with extracted information
        """
        if not self.service:
            raise Exception("Not authenticated. Call authenticate() first.")

        # Build Gmail search query
        # Epoch seconds preserve the selected start time.
        timestamp = int(start_datetime.timestamp())
        from_email = PAYMENT_SOURCES.get(source, 'venmo@venmo.com')
        query = f'from:{from_email} after:{timestamp}'

        # Get messages
        messages = self._get_messages(query)

        # Extract payment details from each message
        payments = []
        print(f"Found {len(messages)} {source.capitalize()} emails total")

        for message in messages:
            if source == 'venmo':
                payment = self._extract_venmo_payment(message)
                if payment:
                    # Only include incoming payments
                    if payment['type'] != 'incoming':
                        continue

                    # Filter by category/keywords
                    if self._matches_category(payment, category, custom_keywords):
                        payments.append(payment)
            elif source == 'zelle':
                # Zelle emails may contain multiple payments in one email
                zelle_payments = self._extract_zelle_payments(message)
                for payment in zelle_payments:
                    if self._matches_category(payment, category, custom_keywords):
                        payments.append(payment)

        return payments

    def _get_messages(self, query: str) -> List[Dict]:
        """Get messages from Gmail based on query"""
        full_messages = []
        page_token = None
        while True:
            results = self.service.users().messages().list(
                userId='me', q=query, pageToken=page_token
            ).execute()
            for msg in results.get('messages', []):
                full_messages.append(self.service.users().messages().get(
                    userId='me', id=msg['id'], format='full'
                ).execute())
            page_token = results.get('nextPageToken')
            if not page_token:
                return full_messages

    def _extract_venmo_payment(self, message: Dict) -> Optional[Dict]:
        """
        Extract payment details from a Venmo email

        Returns:
            Dict with keys: person, amount, date, transaction_id, note, type
        """
        try:
            # Get headers
            headers = message['payload']['headers']
            subject = self._get_header(headers, 'Subject')
            date_str = self._get_header(headers, 'Date')

            # Parse date
            email_date = parsedate_to_datetime(date_str)

            # Get email body
            body = self._get_email_body(message['payload'])

            # Extract payment info from subject
            # Pattern 1: "You paid [Name] $[Amount]" (outgoing)
            outgoing_match = re.search(r'You paid (.+?) \$' + AMOUNT_PATTERN, subject)
            # Pattern 2: "[Name] paid you $[Amount]" (incoming)
            incoming_match = re.search(r'(.+?) paid you \$' + AMOUNT_PATTERN, subject)

            if outgoing_match:
                person = outgoing_match.group(1)
                amount = float(outgoing_match.group(2).replace(',', ''))
                payment_type = "outgoing"
            elif incoming_match:
                person = incoming_match.group(1)
                amount = float(incoming_match.group(2).replace(',', ''))
                payment_type = "incoming"
            else:
                # Not a payment email we recognize
                return None

            # Extract transaction ID from body
            transaction_id = self._extract_transaction_id(body)

            # Extract payment note/description (the reason for payment)
            note = self._extract_payment_note(body)

            return {
                'message_id': message.get('id'),
                'source': 'venmo',
                'person': person,
                'amount': amount,
                'date': email_date.isoformat(),
                'transaction_id': transaction_id,
                'note': note or '',
                'subject': subject,
                'type': payment_type,
            }

        except Exception as e:
            print(f"Error extracting Venmo payment: {e}")
            return None

    def _extract_zelle_payments(self, message: Dict) -> List[Dict]:
        """
        Extract Zelle payments from Wells Fargo email
        Wells Fargo Zelle emails may contain multiple payment notifications

        Returns:
            List of payment dictionaries
        """
        payments = []
        try:
            # Get headers
            headers = message['payload']['headers']
            subject = self._get_header(headers, 'Subject')
            date_str = self._get_header(headers, 'Date')

            # Parse date
            email_date = parsedate_to_datetime(date_str)

            # Get email body
            body = self._get_email_body(message['payload'])

            incoming_pattern = r'([A-Z][A-Z\s]+?)\s+sent you \$' + AMOUNT_PATTERN
            # Memo values can be uppercase, just like wrapped sender names.
            memo_pattern = (r'(?i:Memo|Message|Note):\s*'
                            r'(?![A-Z][A-Z \t]+?\s+sent you \$)[^\r\n]*')
            matches = [match for match in re.finditer(memo_pattern + '|' + incoming_pattern, body)
                       if match.group(1) is not None]

            for payment_index, match in enumerate(matches):
                # Clean up the person's name - remove extra whitespace
                person = ' '.join(match.group(1).strip().split())
                amount = float(match.group(2).replace(',', ''))

                end = matches[payment_index + 1].start() if payment_index + 1 < len(matches) else len(body)
                note = self._extract_zelle_note(body[match.end():end])

                payments.append({
                    'message_id': message.get('id'),
                    'payment_index': payment_index,
                    'person': person,
                    'amount': amount,
                    'date': email_date.isoformat(),
                    'transaction_id': None,  # Zelle doesn't expose transaction IDs in emails
                    'note': note or '',
                    'subject': subject,
                    'type': 'incoming',
                    'source': 'zelle'
                })

        except Exception as e:
            print(f"Error extracting Zelle payments: {e}")

        return payments

    def _extract_zelle_note(self, snippet: str) -> Optional[str]:
        """
        Extract the memo/note from Zelle payment in body text
        """
        patterns = [
            r'Memo:\s*([^\n\r]*)',
            r'Message:\s*([^\n\r]*)',
            r'Note:\s*([^\n\r]*)',
        ]

        for pattern in patterns:
            match = re.search(pattern, snippet, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _get_email_body(self, payload: Dict) -> str:
        """Extract email body from message payload"""
        disposition = self._get_header(payload.get('headers', []), 'Content-Disposition')
        if payload.get('filename') or disposition.lower().startswith('attachment'):
            return ''
        mime_type = payload.get('mimeType', 'text/plain').lower()
        parts = payload.get('parts', [])
        if parts:
            if mime_type == 'multipart/alternative':
                parts = sorted(parts, key=lambda part: part.get('mimeType') != 'text/plain')
                for part in parts:
                    text = self._get_email_body(part)
                    if text.strip():
                        return text
                return ''
            return '\n'.join(filter(None, (self._get_email_body(part) for part in parts)))

        data = payload.get('body', {}).get('data')
        if not data or mime_type not in ('text/plain', 'text/html'):
            return ''
        try:
            text = base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)).decode('utf-8')
        except (ValueError, UnicodeDecodeError):
            return ''
        if mime_type == 'text/html':
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, 'html.parser')
            for element in soup(['script', 'style', 'head']):
                element.decompose()
            for element in soup.find_all(['br', 'div', 'p', 'tr', 'li']):
                element.insert_before('\n')
                element.insert_after('\n')
            text = soup.get_text(separator=' ')
            text = '\n'.join(' '.join(line.split()) for line in text.splitlines())
        return text

    def _extract_transaction_id(self, body: str) -> Optional[str]:
        """Extract transaction ID from email body"""
        match = re.search(r'Transaction ID[:\s]*(\d+)', body)
        if match:
            return match.group(1)
        return None

    def _extract_payment_note(self, body: str) -> Optional[str]:
        """
        Extract the payment note/description from email body
        This is where users add what the payment is for
        """
        body_clean = ' '.join(body.split())
        transaction = re.search(
            r'\$' + AMOUNT_PATTERN + r'\s*(.*?)\s*(?:Money credited|See transaction|$)',
            body_clean, re.IGNORECASE,
        )
        if transaction:
            return transaction.group(2).strip() or None
        labeled = re.search(
            r"(?:^|\n)[ \t]*(?:For\b|Note:|What's it for\?)[ \t]*(.*?)(?=\n|See transaction|Money credited|$)",
            body, re.IGNORECASE,
        )
        if labeled:
            return labeled.group(1).strip() or None
        fallback = re.search(r'^(.*?)\s*See transaction', body_clean, re.IGNORECASE)
        if fallback:
            return fallback.group(1).strip() or None
        return None

    def _get_header(self, headers: List[Dict], name: str) -> str:
        """Get header value by name"""
        for header in headers:
            if header['name'].lower() == name.lower():
                return header['value']
        return ''

    def _matches_category(self, payment: Dict, category: str,
                         custom_keywords: Optional[str] = None) -> bool:
        """
        Check if payment matches the category/keywords

        Args:
            payment: Payment dictionary
            category: Category (retreat, dues, or other)
            custom_keywords: Custom keywords if category is 'other'

        Returns:
            True if payment matches, False otherwise
        """
        # Get the text to search (note, subject, person)
        search_text = (
            f"{payment.get('note', '')} "
            f"{payment.get('subject', '')} "
            f"{payment.get('person', '')}"
        ).lower()

        if category == 'other' and custom_keywords:
            # Split custom keywords by comma
            keywords = [kw.strip().lower() for kw in custom_keywords.split(',') if kw.strip()]
            return not keywords or any(keyword in search_text for keyword in keywords)

        elif category in CATEGORY_KEYWORDS:
            # Check if any preset keyword matches
            keywords = CATEGORY_KEYWORDS[category]
            return any(keyword.lower() in search_text for keyword in keywords)

        # If no keywords, include all
        return True


def scrape_emails(email: str, start_datetime: datetime,
                 category: str, keywords: Optional[str] = None, source: str = 'venmo') -> List[Dict]:
    """
    Main function to scrape payment emails (Venmo or Zelle)

    Args:
        email: Gmail address
        start_datetime: Start date/time to search from
        category: Category (retreat, dues, or other)
        keywords: Custom keywords if category is 'other'
        source: Payment source ('venmo' or 'zelle')

    Returns:
        List of payment dictionaries
    """
    scraper = VenmoEmailScraper(email)
    try:
        scraper.authenticate()
    except ScraperError:
        raise
    except Exception as exc:
        raise ScraperError('authorization_failed') from exc
    payments = scraper.search_payment_emails(start_datetime, category, keywords, source)
    return payments

