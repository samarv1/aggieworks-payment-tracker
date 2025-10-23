"""
CSV handler for saving and updating payment data
"""
import csv
import os
from typing import List, Dict
from datetime import datetime


CSV_FILENAME = "venmo_payments.csv"
CSV_HEADERS = [
    'Person',
    'Date',
    'Description',
    'Amount'
]


def save_payments_to_csv(payments: List[Dict], category: str) -> str:
    """
    Save payments to CSV file. If file exists, update it with new payments.
    
    Args:
        payments: List of payment dictionaries
        category: Category used for filtering
    
    Returns:
        Path to the CSV file
    """
    csv_path = os.path.join(os.path.dirname(__file__), CSV_FILENAME)
    
    # Read existing payments if file exists
    # Use a unique key: Person + Date + Amount to detect duplicates
    existing_payments = {}
    if os.path.exists(csv_path):
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Create unique key from person, date, amount
                key = f"{row['Person']}|{row['Date']}|{row['Amount']}"
                existing_payments[key] = row
    
    # Add/update with new payments
    for payment in payments:
        person = payment.get('person', '')
        date = _format_date(payment.get('date'))
        amount = payment.get('amount', 0)
        
        # Create unique key
        key = f"{person}|{date}|${amount:.2f}"
        
        existing_payments[key] = {
            'Person': person,
            'Date': date,
            'Description': payment.get('note', ''),
            'Amount': f"${amount:.2f}"
        }
    
    # Write all payments back to CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        
        # Sort by date (newest first)
        sorted_payments = sorted(
            existing_payments.values(),
            key=lambda x: x['Date'],
            reverse=True
        )
        writer.writerows(sorted_payments)
    
    print(f"CSV file saved: {csv_path}")
    print(f"Total payments in CSV: {len(existing_payments)}")
    
    return csv_path


def _format_date(iso_date: str) -> str:
    """Format ISO date to readable format"""
    try:
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime('%Y-%m-%d %I:%M %p')
    except:
        return iso_date


def get_csv_path() -> str:
    """Get the path to the CSV file"""
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)


def csv_exists() -> bool:
    """Check if CSV file exists"""
    return os.path.exists(get_csv_path())


def get_payment_count() -> int:
    """Get the number of payments in the CSV"""
    if not csv_exists():
        return 0
    
    with open(get_csv_path(), 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return sum(1 for _ in reader)

