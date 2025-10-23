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

# Category keywords mapping
CATEGORY_KEYWORDS = {
    'retreat': ['retreat', 'retreat payment', 'fall retreat', 'spring retreat', 'annual retreat'],
    'dues': ['dues', 'membership dues', 'club dues', 'monthly dues', 'semester dues'],
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
        
        # Token file stores user's access and refresh tokens
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
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
            
            # Save credentials for next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('gmail', 'v1', credentials=creds)
        return True
    
    def search_venmo_emails(self, start_datetime: datetime, category: str, 
                           custom_keywords: Optional[str] = None) -> List[Dict]:
        """
        Search for Venmo emails and extract payment information
        
        Args:
            start_datetime: Start date/time to search from
            category: Category to filter (retreat, dues, or other)
            custom_keywords: Custom keywords if category is 'other'
        
        Returns:
            List of payment dictionaries with extracted information
        """
        if not self.service:
            raise Exception("Not authenticated. Call authenticate() first.")
        
        # Build Gmail search query
        # Format: from:venmo@venmo.com after:YYYY/MM/DD
        date_str = start_datetime.strftime('%Y/%m/%d')
        query = f'from:venmo@venmo.com after:{date_str}'
        
        # Get messages
        messages = self._get_messages(query)
        
        # Extract payment details from each message
        payments = []
        print(f"Found {len(messages)} Venmo emails total")
        
        for message in messages:
            payment = self._extract_payment_details(message)
            if payment:
                # Only include incoming payments
                if payment['type'] != 'incoming':
                    continue
                
                # Filter by category/keywords
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
    
    def _extract_payment_details(self, message: Dict) -> Optional[Dict]:
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
            print(f"Error extracting payment details: {e}")
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
            # Pattern: "Starbucks See transaction" or just the word before "See transaction"
            r'(\w+(?:\s+\w+){0,5}?)\s*See transaction',
            # Pattern: Between dollar amount and other text
            r'\$[\d,]+\.\d{2}\s+([A-Za-z0-9\s]+?)\s+(?:Money credited|See transaction)',
            # Pattern: After "For" keyword
            r'For\s+(.+?)(?:\n|\.|$)',
            # Pattern: After "Note:" keyword
            r'Note:\s+(.+?)(?:\n|\.|$)',
            # Pattern: "What's it for?" question
            r'What\'s it for\?\s+(.+?)(?:\n|\.|$)',
            # Pattern: Look for text between paid you and See transaction
            r'paid you\s+\$[\d,]+\.\d{2}\s+(.+?)\s+(?:See|Money)',
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
                 category: str, keywords: Optional[str] = None) -> List[Dict]:
    """
    Main function to scrape Venmo emails
    
    Args:
        email: Gmail address
        password: Password (not used for OAuth2)
        start_datetime: Start date/time to search from
        category: Category (retreat, dues, or other)
        keywords: Custom keywords if category is 'other'
    
    Returns:
        List of payment dictionaries
    """
    scraper = VenmoEmailScraper(email, password)
    scraper.authenticate()
    payments = scraper.search_venmo_emails(start_datetime, category, keywords)
    return payments

