"""Save the latest local export, accumulating only within one search context."""
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from functools import wraps
from threading import RLock
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple

CSV_FILENAME = "member_to_DoF_payments.csv"
CSV_HEADERS = ['Person', 'Date', 'Description', 'Amount']
CSV_LOCK = RLock()


def _locked(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with CSV_LOCK:
            return function(*args, **kwargs)
    return wrapped


def _amount(value) -> Decimal:
    amount = Decimal(str(value).replace('$', '').replace(',', ''))
    if not amount.is_finite():
        raise ValueError("Payment amount must be finite")
    return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _date_key(value: str) -> float:
    """Compare actual instants, with naive local dates treated consistently as UTC."""
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return float('-inf')


def _payment_key(payment: Dict) -> str:
    # Gmail IDs are stable within an account; context below isolates accounts.
    identifier = payment.get('message_id') or payment.get('transaction_id')
    if identifier:
        return json.dumps(['id', payment.get('source', ''), str(identifier),
                           payment.get('payment_index', 0)])
    # Legacy callers have no ID. Include the note and unrounded timestamp to
    # avoid merging unrelated payments just because their displayed dates match.
    return json.dumps(['legacy', payment.get('source', ''), payment.get('person', ''),
                       payment.get('date', ''), payment.get('note', ''),
                       str(_amount(payment.get('amount', 0)))])


@_locked
def save_payments_to_csv(payments: List[Dict], category: str,
                         start_datetime: Optional[str] = None,
                         source: Optional[str] = None, *,
                         email: Optional[str] = None,
                         custom_keywords: Optional[str] = None) -> Tuple[str, float]:
    """Replace the local CSV when account or any filter changes.

    Exact repeated searches accumulate using stable message IDs. Missing account
    context, old metadata, or damaged metadata always starts a fresh export.
    The sidecar retains IDs without adding implementation columns to the CSV.
    """
    csv_path = get_csv_path()
    metadata_path = os.path.join(os.path.dirname(__file__), 'csv_metadata.txt')
    context = {'email': email.strip().lower() if email else None,
               'category': category, 'custom_keywords': custom_keywords or '',
               'start_datetime': start_datetime, 'source': source}
    existing = {}
    if context['email'] and os.path.exists(csv_path):
        try:
            with open(metadata_path, encoding='utf-8') as handle:
                metadata = json.load(handle)
            with open(csv_path, 'rb') as handle:
                csv_hash = hashlib.sha256(handle.read()).hexdigest()
            if (metadata.get('version') == 1 and metadata.get('context') == context
                    and metadata.get('csv_sha256') == csv_hash
                    and isinstance(metadata.get('payments'), dict)):
                existing = metadata['payments']
        except (OSError, ValueError, AttributeError):
            pass

    for payment in payments:
        existing[_payment_key(payment)] = {
            'person': payment.get('person', ''), 'date': payment.get('date', ''),
            'note': payment.get('note', ''),
            'amount': str(_amount(payment.get('amount', 0)))
        }
    ordered = sorted(existing.values(), key=lambda p: _date_key(p['date']), reverse=True)
    total = sum((_amount(p['amount']) for p in ordered), Decimal('0.00'))
    with open(csv_path, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for payment in ordered:
            writer.writerow({'Person': payment['person'], 'Date': _format_date(payment['date']),
                             'Description': payment['note'], 'Amount': f"${_amount(payment['amount']):.2f}"})
        writer.writerow({'Person': '', 'Date': '', 'Description': 'TOTAL', 'Amount': f'${total:.2f}'})
    with open(csv_path, 'rb') as handle:
        csv_hash = hashlib.sha256(handle.read()).hexdigest()
    with open(metadata_path, 'w', encoding='utf-8') as handle:
        json.dump({'version': 1, 'context': context, 'payments': existing,
                   'csv_sha256': csv_hash}, handle)
    return csv_path, float(total)


def _format_date(iso_date: str) -> str:
    try:
        return datetime.fromisoformat(iso_date).strftime('%Y-%m-%d %I:%M %p')
    except (ValueError, TypeError):
        return iso_date or ''


def get_csv_path() -> str:
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)


def csv_exists() -> bool:
    return os.path.exists(get_csv_path())


@_locked
def get_payment_count() -> int:
    if not csv_exists():
        return 0
    with open(get_csv_path(), newline='', encoding='utf-8') as handle:
        # Only the final generated total has both person and date empty.
        return sum(1 for row in csv.DictReader(handle)
                   if not (row.get('Description') == 'TOTAL'
                           and not row.get('Person') and not row.get('Date')))
