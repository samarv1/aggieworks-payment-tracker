import csv
import os
import sys
import tempfile
import json
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import csv_handler


class CsvTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.location = patch.object(csv_handler, '__file__', os.path.join(self.temp.name, 'csv_handler.py'))
        self.location.start()
        self.addCleanup(self.location.stop)
        self.context = dict(category='dues', start_datetime='2026-01-01 00:00',
                            source='venmo', email='test@example.invalid', custom_keywords='dues')

    def payment(self, identifier='one', **fields):
        return dict(dict(message_id=identifier, person='Example Member',
                         date='2026-01-02T09:00:00', note='dues', amount='0.10'), **fields)

    def save(self, payments, **context):
        return csv_handler.save_payments_to_csv(payments, **dict(self.context, **context))

    def rows(self):
        with open(csv_handler.get_csv_path(), newline='') as handle:
            return list(csv.DictReader(handle))

    def test_repeated_message_is_deduplicated_but_distinct_identical_payments_survive(self):
        self.save([self.payment()])
        _, total = self.save([self.payment(), self.payment('two')])
        self.assertEqual(csv_handler.get_payment_count(), 2)
        self.assertEqual(total, 0.2)
        self.assertEqual(self.rows()[-1]['Amount'], '$0.20')

    def test_distinct_payments_in_same_message_survive_repeated_scrapes(self):
        payments = [self.payment(source='zelle', payment_index=0),
                    self.payment(source='zelle', payment_index=1)]
        self.save(payments)
        self.save(payments)
        self.assertEqual(csv_handler.get_payment_count(), 2)

    def test_each_context_change_resets_export(self):
        for field, value in dict(email='another@example.invalid', category='merch',
                                 custom_keywords='shirt', start_datetime='2026-02-01 00:00',
                                 source='zelle').items():
            with self.subTest(field=field):
                self.save([self.payment('old')])
                self.save([self.payment('new')], **{field: value})
                self.assertEqual(csv_handler.get_payment_count(), 1)

    def test_missing_account_never_accumulates(self):
        self.save([self.payment('old')], email=None)
        self.save([self.payment('new')], email=None)
        self.assertEqual(csv_handler.get_payment_count(), 1)

    def test_sorts_chronologically_across_noon_and_timezones(self):
        self.save([self.payment('a', person='morning', date='2026-01-02T09:00:00'),
                   self.payment('b', person='afternoon', date='2026-01-02T13:00:00'),
                   self.payment('c', person='latest', date='2026-01-02T08:00:00-08:00')])
        self.assertEqual([r['Person'] for r in self.rows()[:-1]], ['latest', 'afternoon', 'morning'])

    def test_legacy_metadata_is_not_reused(self):
        self.save([self.payment('old')])
        with open(os.path.join(self.temp.name, 'csv_metadata.txt'), 'w') as handle:
            handle.write('2026-01-01 00:00|venmo')
        self.save([self.payment('new')])
        self.assertEqual(csv_handler.get_payment_count(), 1)

    def test_empty_new_search_removes_previous_results(self):
        self.save([self.payment()])
        _, total = self.save([], category='merch')
        self.assertEqual(csv_handler.get_payment_count(), 0)
        self.assertEqual(total, 0)

    def test_decimal_rounding_and_total_note_count(self):
        self.save([self.payment('a', amount='2.675', note='TOTAL'), self.payment('b', amount='0.10')])
        self.assertEqual(self.rows()[-1]['Amount'], '$2.78')
        self.assertEqual(csv_handler.get_payment_count(), 2)

    def test_modified_csv_does_not_reuse_old_sidecar(self):
        self.save([self.payment('old')])
        with open(csv_handler.get_csv_path(), 'a') as handle:
            handle.write('\n')
        self.save([self.payment('new')])
        self.assertEqual(csv_handler.get_payment_count(), 1)

    def test_formula_prefixes_are_escaped_only_in_export(self):
        values = ['=1+1', '+1+1', '-1+1', '@SUM(A1)', '  =1+1', '\t=1+1',
                  '\r=1+1', '\n=1+1', '\x00=1+1', '\u00a0=1+1', '\u2003\x00 =1+1', '＝1+1',
                  '＋1+1', '－1+1', '＠SUM(A1)', '=1+1,"quoted"\nnext line']
        for value in values:
            with self.subTest(value=value):
                payment = self.payment(person=value, note=value, date=value)
                self.save([payment])
                self.save([payment])
                row = self.rows()[0]
                for column in ['Person', 'Description', 'Date']:
                    self.assertEqual(row[column], "'" + value)
                self.assertEqual(self.rows()[-1]['Amount'], '$0.10')
                with open(os.path.join(self.temp.name, 'csv_metadata.txt')) as handle:
                    stored = next(iter(json.load(handle)['payments'].values()))
                self.assertEqual(stored['note'], value)

    def test_ordinary_text_and_csv_delimiters_round_trip(self):
        note = 'Dues, "fall"\nThanks!'
        self.save([self.payment(person='Taylor Example', note=note)])
        self.assertEqual(self.rows()[0]['Person'], 'Taylor Example')
        self.assertEqual(self.rows()[0]['Description'], note)


if __name__ == '__main__':
    unittest.main()
