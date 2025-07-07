# flight_agent/booking_import.py
import imaplib
import email
from datetime import datetime, timedelta
import re
from typing import List, Dict, Optional
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
from .models import create_booking, get_user_by_email, EmailConnection, SessionLocal



# Turn the BookingImporter class methods into tool functions:
def scan_email_for_bookings(user_email: str, password: str) -> str:
    """Tool function for booking import agent"""
    importer = BookingImporter()
    bookings = importer.import_from_imap(user_email, password)
    return f"Found {len(bookings)} bookings: {bookings}"


class BookingImporter:
    """Import flight bookings from email"""
    
    def __init__(self):
        self.airline_parsers = {
            'united.com': self._parse_united_email,
            'aa.com': self._parse_american_email,
            'delta.com': self._parse_delta_email,
            'southwest.com': self._parse_southwest_email,
            'jetblue.com': self._parse_jetblue_email
        }
        
        # Common patterns for flight extraction
        self.patterns = {
            'pnr': [
                r'Confirmation (?:Number|Code)[:\s]+([A-Z0-9]{6})',
                r'Record Locator[:\s]+([A-Z0-9]{6})',
                r'Booking Reference[:\s]+([A-Z0-9]{6})',
                r'Reservation Code[:\s]+([A-Z0-9]{6})'
            ],
            'flight': [
                r'Flight[:\s]+([A-Z]{2})\s*(\d{1,4})',
                r'([A-Z]{2})\s*(\d{1,4})\s*(?:Operated|Marketing)',
                r'Flight Number[:\s]+([A-Z]{2})\s*(\d{1,4})'
            ],
            'date': [
                r'(\w+day,\s+\w+\s+\d{1,2},\s+\d{4})',
                r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
                r'(\w{3}\s+\d{1,2},\s+\d{4})'
            ],
            'route': [
                r'([A-Z]{3})\s*(?:to|-|→)\s*([A-Z]{3})',
                r'From[:\s]+([A-Z]{3})\s+To[:\s]+([A-Z]{3})',
                r'Depart[:\s]+([A-Z]{3})\s+Arrive[:\s]+([A-Z]{3})'
            ],
            'time': [
                r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))',
                r'Departs?[:\s]+(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))'
            ]
        }
    
    def import_from_gmail(self, user_email: str, credentials: Credentials) -> List[Dict]:
        """Import bookings from Gmail using OAuth"""
        try:
            service = build('gmail', 'v1', credentials=credentials)
            bookings = []
            
            # Search for airline emails in the last 6 months
            query = self._build_gmail_query()
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=50
            ).execute()
            
            messages = results.get('messages', [])
            
            for message in messages:
                msg = service.users().messages().get(
                    userId='me',
                    id=message['id']
                ).execute()
                
                booking = self._parse_gmail_message(msg)
                if booking:
                    bookings.append(booking)
            
            return bookings
            
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def import_from_imap(self, email_address: str, password: str, 
                        imap_server: str = "imap.gmail.com") -> List[Dict]:
        """Import bookings using IMAP (app-specific password)"""
        bookings = []
        
        try:
            # Connect to email server
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(email_address, password)
            mail.select('inbox')
            
            # Search for airline emails
            airline_domains = ['united.com', 'aa.com', 'delta.com', 'southwest.com']
            
            for domain in airline_domains:
                # Search emails from last 6 months
                date_6_months_ago = (datetime.now() - timedelta(days=180)).strftime("%d-%b-%Y")
                search_criteria = f'(FROM "@{domain}" SINCE {date_6_months_ago})'
                
                status, messages = mail.search(None, search_criteria)
                
                for msg_id in messages[0].split()[-20:]:  # Process last 20 emails per airline
                    try:
                        status, msg_data = mail.fetch(msg_id, '(RFC822)')
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        
                        booking = self._parse_email_message(msg, domain)
                        if booking:
                            bookings.append(booking)
                            
                    except Exception as e:
                        print(f"Error parsing email {msg_id}: {e}")
                        continue
            
            mail.close()
            mail.logout()
            
        except Exception as e:
            print(f"IMAP connection error: {e}")
        
        return bookings
    
    def _build_gmail_query(self) -> str:
        """Build Gmail search query for airline emails"""
        airlines = [
            'from:united.com',
            'from:aa.com', 
            'from:delta.com',
            'from:southwest.com',
            'from:jetblue.com'
        ]
        
        keywords = [
            'confirmation',
            'itinerary',
            'boarding pass',
            'e-ticket'
        ]
        
        # Combine with OR
        airline_query = f"({' OR '.join(airlines)})"
        keyword_query = f"({' OR '.join(keywords)})"
        date_query = "newer_than:6m"  # Last 6 months
        
        return f"{airline_query} {keyword_query} {date_query}"
    
    def _parse_gmail_message(self, msg: dict) -> Optional[Dict]:
        """Parse Gmail API message"""
        try:
            # Extract email content
            payload = msg['payload']
            headers = {h['name']: h['value'] for h in payload.get('headers', [])}
            
            sender = headers.get('From', '').lower()
            subject = headers.get('Subject', '')
            
            # Get body
            body = self._extract_gmail_body(payload)
            
            # Determine airline
            airline_domain = None
            for domain in self.airline_parsers.keys():
                if domain in sender:
                    airline_domain = domain
                    break
            
            if not airline_domain or not body:
                return None
            
            # Parse based on airline
            return self.airline_parsers[airline_domain](subject, body, headers)
            
        except Exception as e:
            print(f"Error parsing Gmail message: {e}")
            return None
    
    def _extract_gmail_body(self, payload: dict) -> str:
        """Extract body from Gmail payload"""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body']['data']
                    body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                elif part['mimeType'] == 'text/html' and not body:
                    data = part['body']['data']
                    body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        elif payload['body'].get('data'):
            body = base64.urlsafe_b64decode(
                payload['body']['data']
            ).decode('utf-8', errors='ignore')
        
        return body
    
    def _parse_email_message(self, msg: email.message.Message, 
                           airline_domain: str) -> Optional[Dict]:
        """Parse email message from IMAP"""
        try:
            subject = msg['subject']
            sender = msg['from'].lower()
            
            # Get email body
            body = self._get_email_body(msg)
            
            if not body:
                return None
            
            # Parse based on airline
            return self.airline_parsers[airline_domain](
                subject, body, dict(msg.items())
            )
            
        except Exception as e:
            print(f"Error parsing email: {e}")
            return None
    
    def _get_email_body(self, msg: email.message.Message) -> str:
        """Extract text body from email message"""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                elif content_type == "text/html" and not body:
                    # Could parse HTML here if needed
                    body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        
        return body
    
    def _extract_with_patterns(self, text: str, pattern_list: List[str]) -> Optional[str]:
        """Extract first match from list of patterns"""
        for pattern in pattern_list:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1) if match.groups() else match.group(0)
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats"""
        date_formats = [
            "%A, %B %d, %Y",  # Monday, January 15, 2024
            "%B %d, %Y",      # January 15, 2024
            "%b %d, %Y",      # Jan 15, 2024
            "%m/%d/%Y",       # 01/15/2024
            "%m-%d-%Y",       # 01-15-2024
            "%Y-%m-%d",       # 2024-01-15
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None
    
    def _parse_united_email(self, subject: str, body: str, headers: dict) -> Optional[Dict]:
        """Parse United Airlines confirmation email"""
        try:
            # Check if it's a confirmation email
            if 'confirmation' not in subject.lower() and 'itinerary' not in subject.lower():
                return None
            
            # Extract PNR
            pnr = self._extract_with_patterns(body, self.patterns['pnr'])
            if not pnr:
                return None
            
            # Extract flights
            bookings = []
            flight_matches = re.findall(r'UA\s*(\d{1,4})', body)
            
            # Extract routes
            route_matches = re.findall(r'([A-Z]{3})\s*to\s*([A-Z]{3})', body)
            
            # Extract dates
            date_matches = re.findall(self.patterns['date'][0], body)
            
            # Combine into bookings
            for i, flight_num in enumerate(flight_matches):
                if i < len(route_matches) and i < len(date_matches):
                    departure_date = self._parse_date(date_matches[i])
                    if departure_date and departure_date > datetime.now():
                        bookings.append({
                            'pnr': pnr,
                            'airline': 'United',
                            'flight_number': f'UA{flight_num}',
                            'departure_date': departure_date,
                            'origin': route_matches[i][0],
                            'destination': route_matches[i][1],
                            'raw_data': {
                                'subject': subject,
                                'sender': headers.get('From', '')
                            }
                        })
            
            return bookings[0] if bookings else None
            
        except Exception as e:
            print(f"Error parsing United email: {e}")
            return None
    
    def _parse_american_email(self, subject: str, body: str, headers: dict) -> Optional[Dict]:
        """Parse American Airlines confirmation email"""
        # Similar implementation to United
        # Adjust patterns for AA's email format
        pass
    
    def _parse_delta_email(self, subject: str, body: str, headers: dict) -> Optional[Dict]:
        """Parse Delta confirmation email"""
        # Similar implementation
        pass
    
    def _parse_southwest_email(self, subject: str, body: str, headers: dict) -> Optional[Dict]:
        """Parse Southwest confirmation email"""
        # Similar implementation
        pass
    
    def _parse_jetblue_email(self, subject: str, body: str, headers: dict) -> Optional[Dict]:
        """Parse JetBlue confirmation email"""
        # Similar implementation
        pass


def setup_email_connection(user_id: str, email_address: str, 
                         app_password: str = None, oauth_token: str = None):
    """Setup email connection for a user"""
    db = SessionLocal()
    try:
        connection = EmailConnection(
            id=f"email_{user_id}_{datetime.now().timestamp()}",
            user_id=user_id,
            email_provider='gmail',
            email_address=email_address,
            access_token=app_password or oauth_token,
            last_sync=datetime.utcnow()
        )
        db.add(connection)
        db.commit()
        return connection
    finally:
        db.close()


def sync_user_bookings(user_email: str, email_password: str = None) -> int:
    """Sync bookings for a user from their email"""
    # Get or create user
    user = get_user_by_email(user_email)
    if not user:
        from .models import create_user
        user = create_user(user_email)
    
    # Import bookings
    importer = BookingImporter()
    
    if email_password:
        # Use IMAP
        bookings = importer.import_from_imap(user_email, email_password)
    else:
        # Would need OAuth credentials here
        print("OAuth not implemented in this example")
        return 0
    
    # Save bookings to database
    saved_count = 0
    for booking_data in bookings:
        try:
            create_booking(user.user_id, booking_data)
            saved_count += 1
        except Exception as e:
            print(f"Error saving booking: {e}")
            continue
    
    print(f"Imported {saved_count} bookings for {user_email}")
    return saved_count