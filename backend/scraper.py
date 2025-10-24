"""
Gmail scraper for Venmo payment emails
"""
import re
from datetime import datetime
from typing import List, Dict, Optional
import base64
from email.utils import parsedate_to_datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
import os.path
import pickle

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
    
    def __init__(self, email: str, password: str = None):
        """
        Initialize the scraper
        
        Args:
            email: Gmail address
            password: Not used for OAuth2, kept for API compatibility
        """
        self.email = email
        self.service = None
    
    def authenticate(self):
        """Authenticate with Gmail API using OAuth2"""
        creds = None
        
        # Create email-specific token filename
        # Replace @ and . to make it filename-safe
        safe_email = self.email.replace('@', '_at_').replace('.', '_')
        token_file = f'token_{safe_email}.pickle'
        
        # Token file stores user's access and refresh tokens
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # If credentials are invalid or don't exist, let user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # For now, we'll need to set up OAuth2 credentials
                # This requires a credentials.json file from Google Cloud Console
                if os.path.exists('credentials.json'):
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                else:
                    raise Exception(
                        "OAuth2 credentials file not found. "
                        "Please set up Gmail API credentials from Google Cloud Console"
                    )
            
            # Save credentials for next run with email-specific filename
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('gmail', 'v1', credentials=creds)
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
        # Format: from:email@domain.com after:YYYY/MM/DD
        date_str = start_datetime.strftime('%Y/%m/%d')
        from_email = PAYMENT_SOURCES.get(source, 'venmo@venmo.com')
        query = f'from:{from_email} after:{date_str}'
        
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
        try:
            results = self.service.users().messages().list(
                userId='me', 
                q=query
            ).execute()
            
            messages = results.get('messages', [])
            
            # Get full message details
            full_messages = []
            for msg in messages:
                message = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                full_messages.append(message)
            
            return full_messages
        
        except Exception as e:
            print(f"Error fetching messages: {e}")
            return []
    
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
            outgoing_match = re.search(r'You paid (.+?) \$(\d+\.\d{2})', subject)
            # Pattern 2: "[Name] paid you $[Amount]" (incoming)
            incoming_match = re.search(r'(.+?) paid you \$(\d+\.\d{2})', subject)
            
            if outgoing_match:
                person = outgoing_match.group(1)
                amount = float(outgoing_match.group(2))
                payment_type = "outgoing"
            elif incoming_match:
                person = incoming_match.group(1)
                amount = float(incoming_match.group(2))
                payment_type = "incoming"
            else:
                # Not a payment email we recognize
                return None
            
            # Extract transaction ID from body
            transaction_id = self._extract_transaction_id(body)
            
            # Extract payment note/description (the reason for payment)
            note = self._extract_payment_note(body)
            
            return {
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
            
            # Zelle payment patterns in Wells Fargo emails
            # Pattern: "NAME sent you $X.XX"
            # Match only the name (capital letters and spaces), not leading whitespace
            incoming_pattern = r'([A-Z][A-Z\s]+?)\s+sent you \$(\d+\.\d{2})'
            
            matches = re.finditer(incoming_pattern, body)
            
            for match in matches:
                # Clean up the person's name - remove extra whitespace
                person = ' '.join(match.group(1).strip().split())
                amount = float(match.group(2))
                
                # Try to find memo/note nearby (after the match)
                note = self._extract_zelle_note(body, match.end())
                
                payments.append({
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
    
    def _extract_zelle_note(self, body: str, match_position: int) -> Optional[str]:
        """
        Extract the memo/note from Zelle payment in body text
        """
        # Look for "Memo:" within 500 characters after the match
        snippet = body[match_position:match_position + 500]
        
        patterns = [
            r'Memo:\s*([^\n\r]+)',
            r'Message:\s*([^\n\r]+)',
            r'Note:\s*([^\n\r]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, snippet, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _get_email_body(self, payload: Dict) -> str:
        """Extract email body from message payload"""
        body_text = ''
        
        # Direct body
        if 'body' in payload and 'data' in payload['body'] and payload['body']['data']:
            try:
                body_text = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                return body_text
            except Exception:
                pass
        
        # Check parts for multipart messages
        if 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                
                # Recursively check nested parts
                if 'parts' in part:
                    nested_body = self._get_email_body(part)
                    if nested_body:
                        return nested_body
                
                # Check body data
                if 'body' in part and 'data' in part['body'] and part['body']['data']:
                    try:
                        if mime_type == 'text/html':
                            html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                            soup = BeautifulSoup(html, 'html.parser')
                            body_text = soup.get_text()
                            if body_text.strip():
                                return body_text
                        elif mime_type == 'text/plain':
                            body_text = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                            if body_text.strip():
                                return body_text
                    except Exception:
                        pass
        
        return body_text
    
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
        # Clean up whitespace for better matching
        body_clean = ' '.join(body.split())
        
        # Venmo emails may contain the note in different formats
        # Look for common patterns (in order of most specific to least specific)
        patterns = [
            # Pattern: Any text before "See transaction" (no word limit)
            r'([\w\s\-]+?)\s*See transaction',
            # Pattern: Between dollar amount and other text
            r'\$[\d,]+\.\d{2}\s+([\w\s\-]+?)\s+(?:Money credited|See transaction)',
            # Pattern: After "For" keyword
            r'For\s+(.+?)(?:\n|\.|$)',
            # Pattern: After "Note:" keyword
            r'Note:\s+(.+?)(?:\n|\.|$)',
            # Pattern: "What's it for?" question
            r'What\'s it for\?\s+(.+?)(?:\n|\.|$)',
            # Pattern: Look for text between paid you and See transaction
            r'paid you\s+\$[\d,]+\.\d{2}\s+([\w\s\-]+?)\s+(?:See|Money)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, body_clean, re.IGNORECASE)
            if match:
                note = match.group(1).strip()
                # Clean up the note
                note = re.sub(r'\s+', ' ', note)  # Normalize whitespace
                note = note.strip()
                if note and len(note) > 0:
                    return note
        
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
            keywords = [kw.strip().lower() for kw in custom_keywords.split(',')]
            return any(keyword in search_text for keyword in keywords)
        
        elif category in CATEGORY_KEYWORDS:
            # Check if any preset keyword matches
            keywords = CATEGORY_KEYWORDS[category]
            return any(keyword.lower() in search_text for keyword in keywords)
        
        # If no keywords, include all
        return True


def scrape_emails(email: str, password: str, start_datetime: datetime,
                 category: str, keywords: Optional[str] = None, source: str = 'venmo') -> List[Dict]:
    """
    Main function to scrape payment emails (Venmo or Zelle)
    
    Args:
        email: Gmail address
        password: Password (not used for OAuth2)
        start_datetime: Start date/time to search from
        category: Category (retreat, dues, or other)
        keywords: Custom keywords if category is 'other'
        source: Payment source ('venmo' or 'zelle')
    
    Returns:
        List of payment dictionaries
    """
    scraper = VenmoEmailScraper(email, password)
    scraper.authenticate()
    payments = scraper.search_payment_emails(start_datetime, category, keywords, source)
    return payments

