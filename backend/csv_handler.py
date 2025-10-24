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


def save_payments_to_csv(payments: List[Dict], category: str, start_datetime: str = None, source: str = None) -> str:
    """
    Save payments to CSV file. If file exists, update it with new payments.
    
    Args:
        payments: List of payment dictionaries
        category: Category used for filtering
        start_datetime: Start datetime string for the search
        source: Payment source (venmo, zelle, or both)
    
    Returns:
        Path to the CSV file
    """
    csv_path = os.path.join(os.path.dirname(__file__), CSV_FILENAME)
    metadata_path = os.path.join(os.path.dirname(__file__), 'csv_metadata.txt')
    
    # Check if search parameters changed
    existing_payments = {}
    if os.path.exists(csv_path) and os.path.exists(metadata_path):
        # Read last search metadata (datetime|source)
        with open(metadata_path, 'r') as f:
            metadata = f.read().strip()
        
        # If search datetime AND source are the same, accumulate. If different, start fresh.
        current_metadata = f"{start_datetime}|{source}"
        if start_datetime and metadata == current_metadata:
            # Same search - accumulate payments
            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Skip the TOTAL row
                    if row['Description'] == 'TOTAL':
                        continue
                    # Create unique key from person, date, amount
                    key = f"{row['Person']}|{row['Date']}|{row['Amount']}"
                    existing_payments[key] = row
            print(f"Same search parameters - accumulating with existing {len(existing_payments)} payment(s)")
        else:
            # Different search - start fresh
            print(f"Search parameters changed - starting fresh CSV")
    
    # Save current search metadata (datetime|source)
    if start_datetime and source:
        with open(metadata_path, 'w') as f:
            f.write(f"{start_datetime}|{source}")
    
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
    
    # Sort by date (newest first)
    sorted_payments = sorted(
        existing_payments.values(),
        key=lambda x: x['Date'],
        reverse=True
    )
    
    # Calculate total
    total_amount = sum(
        float(p['Amount'].replace('$', '').replace(',', '')) 
        for p in existing_payments.values()
    )
    
    # Write all payments back to CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(sorted_payments)
        
        # Add total row at the bottom
        writer.writerow({
            'Person': '',
            'Date': '',
            'Description': 'TOTAL',
            'Amount': f"${total_amount:.2f}"
        })
    
    print(f"CSV file saved: {csv_path}")
    print(f"Total payments in CSV: {len(existing_payments)}")
    print(f"Total amount: ${total_amount:.2f}")
    
    return csv_path, total_amount


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
    """Get the number of payments in the CSV (excluding TOTAL row)"""
    if not csv_exists():
        return 0
    
    with open(get_csv_path(), 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return sum(1 for row in reader if row.get('Description') != 'TOTAL')

