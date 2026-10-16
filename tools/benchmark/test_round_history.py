import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import round_history as h

HERE = Path(__file__).parent
REVIEWER = 'Independent Reviewer · Example'
SHA = 'a' * 40
WHEN = '2026-10-16T00:00:00Z'


def comment(body, when=WHEN):
    return {'body': body, 'created': when}


def verdict(sha=SHA, text='', signer=REVIEWER):
    return comment(f'**{signer}:** Not approved at {sha}. {text}')


def analyze(comments):
    return h.report(h.extract_events(comments, [REVIEWER]))


class SignalTests(unittest.TestCase):
    def test_owner_and_unlisted_signatures_are_excluded(self):
        for signer in ('Program Owner', 'Build Engineer · Example', 'Unknown Reviewer'):
            with self.subTest(signer=signer):
                self.assertEqual(analyze([verdict(signer=signer)])['verdict_events'], 0)

    def test_quoted_buried_unsigned_and_invisible_signals_are_excluded(self):
        body = verdict()['body']
        for prefix in ('> ', 'Builder summary:\n', '```\n', '\ufeff', '\u200b'):
            with self.subTest(prefix=prefix):
                self.assertEqual(analyze([comment(prefix + body)])['verdict_events'], 0)
        self.assertEqual(analyze([comment(f'Approved at {SHA}')])['verdict_events'], 0)

    def test_sha_grammar_boundaries(self):
        for token in ('a' * 6, 'a' * 41, 'a' * 40 + 'z', '`' + SHA, SHA + '`'):
            with self.subTest(token=token):
                self.assertEqual(analyze([verdict(sha=token)])['verdict_events'], 0)
        for token in ('a' * 7, SHA, '`' + SHA + '`'):
            with self.subTest(token=token):
                self.assertEqual(analyze([verdict(sha=token)])['verdict_events'], 1)

    def test_case_whitespace_and_signature_colon_variants(self):
        for signature in (f'**{REVIEWER}:**', f'**{REVIEWER}**:', f'**{REVIEWER}**'):
            c = comment(f' \n{signature}\nAPPROVED at {SHA.upper()}')
            events = h.extract_events([c], ['  independent   reviewer · example: '])
            self.assertEqual(events[0]['signer'], REVIEWER)
            self.assertEqual(events[0]['sha'], SHA)
            self.assertEqual(events[0]['verdict'], 'approved')

    def test_verdict_must_be_first_after_signature(self):
        for rest in (f'Result: Approved at {SHA}', f'**Approved at {SHA}**', f'Not  approved at {SHA}'):
            self.assertEqual(analyze([comment(f'**{REVIEWER}:** {rest}')])['verdict_events'], 0)

    def test_multiple_explicit_reviewers(self):
        events = h.extract_events([verdict(), verdict(signer='Legacy · PR review')],
                                  [REVIEWER, 'Legacy · PR review'])
        self.assertEqual(len(events), 2)

    def test_empty_reviewer_selection_is_an_error(self):
        for reviewers in ([], [''], ['   ']):
            with self.assertRaises(h.Broken):
                h.extract_events([], reviewers)

    def test_refresh_and_changed_verdict_are_events_not_invented_rounds(self):
        approval = comment(f'**{REVIEWER}:** Approved at {SHA}')
        r = analyze([approval, approval, verdict()])
        self.assertEqual(r['verdict_events'], 3)
        self.assertEqual(r['distinct_reviewed_sha_tokens'], 1)
        self.assertEqual(r['first_approval_event_index'], 1)
        self.assertTrue(r['has_approval_event'])
        for key in ('review_rounds', 'rounds_to_approval', 'class_reopens'):
            self.assertIsNone(r[key])
        self.assertNotIn('approved', r)

    def test_unsorted_input_is_sorted_by_actual_time_including_offsets(self):
        later = comment(f'**{REVIEWER}:** Approved at {SHA}', '2026-10-16T01:00:00Z')
        earlier = verdict()
        earlier['created'] = '2026-10-16T02:00:00+03:00'
        self.assertEqual(analyze([later, earlier])['first_approval_event_index'], 2)


class ObservationTests(unittest.TestCase):
    def test_first_review_with_open_class_is_not_reported_as_reopen(self):
        r = analyze([verdict(text='No class has been closed; parser remains open.')])
        self.assertEqual(r['literal_reopen_phrase_events'], [1])
        self.assertIsNone(r['class_reopens'])
        self.assertNotIn('rounds_a_ledger_likely_catches_as_reopen', r)

    def test_shared_boilerplate_is_labelled_text_overlap(self):
        common = 'Immutable head inspected, evidence checked, tests passed, scope unchanged, independent review. '
        r = analyze([verdict(text=common + 'Pagination loses results.'),
                     verdict(sha='b' * 40, text=common + 'Unicode corrupts labels.')])
        self.assertEqual(len(r['comment_text_overlap']), 1)
        self.assertIsNone(r['class_reopens'])
        self.assertNotIn('recurring_class_flags', r)

    def test_negated_phrase_is_a_literal_match_without_lifecycle_inference(self):
        r = analyze([verdict(text='No class remains open.')])
        self.assertEqual(r['literal_reopen_phrase_events'], [1])
        self.assertIsNone(r['class_reopens'])

    def test_empty_history_and_overlap(self):
        self.assertEqual(analyze([])['verdict_events'], 0)
        self.assertIsNone(analyze([])['first_approval_event_index'])
        self.assertEqual(h.jaccard('the a of', 'test'), 0)
        self.assertEqual(h.jaccard('order missing', 'missing order'), 1)

    def test_invalid_thresholds_fail(self):
        for threshold in (-1, 1.1, float('nan'), float('inf'), -float('inf')):
            with self.assertRaises(h.Broken):
                h.report([], threshold)


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dest = Path(self.temp.name) / 'comments.json'
        self.args = SimpleNamespace(repo='fictional/project', pr=1, out=str(self.dest))

    def fetch(self, response):
        with patch.object(h.subprocess, 'run', return_value=response) as call:
            with contextlib.redirect_stdout(io.StringIO()):
                h.cmd_fetch(self.args)
        return call.call_args

    def test_second_page_verdict_and_unicode_survive_the_production_path(self):
        pages = [[{'body': 'progress', 'created_at': WHEN}] * 100,
                 [{'id': 101, 'body': verdict(text='Español 日本語')['body'], 'created_at': WHEN}]]
        call = self.fetch(SimpleNamespace(returncode=0, stdout=json.dumps(pages), stderr=''))
        self.assertIn('--paginate', call.args[0])
        self.assertIn('--slurp', call.args[0])
        self.assertEqual(call.kwargs['encoding'], 'utf-8')
        saved = json.loads(self.dest.read_text(encoding='utf-8'))
        self.assertEqual(len(saved['comments']), 101)
        self.assertIn('日本語', saved['comments'][-1]['body'])
        self.assertEqual(analyze(saved['comments'])['verdict_events'], 1)
        self.assertEqual(saved['pagination'], 'all_pages_retrieved')
        self.assertEqual(saved['coverage'], 'issue_comments_only')

    def test_followup_page_failure_does_not_publish_a_partial_snapshot(self):
        self.dest.write_text('existing snapshot', encoding='utf-8')
        with self.assertRaises(h.Broken):
            self.fetch(SimpleNamespace(returncode=1, stdout='[[{"body":"partial"}]]', stderr='page 2 failed'))
        self.assertEqual(self.dest.read_text(), 'existing snapshot')

    def test_bad_page_or_comment_shapes_fail_before_output(self):
        for payload in ({}, [1], [[None]], [[{}]], [[{'body': 1, 'created_at': WHEN}]]):
            with self.subTest(payload=payload), self.assertRaises(h.Broken):
                self.fetch(SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=''))
            self.assertFalse(self.dest.exists())

    def test_empty_collection_is_valid(self):
        self.fetch(SimpleNamespace(returncode=0, stdout='[[]]', stderr=''))
        self.assertEqual(json.loads(self.dest.read_text())['comments'], [])

    def test_invalid_repo_and_pr_are_rejected_without_a_subprocess(self):
        with patch.object(h.subprocess, 'run') as call:
            for repo, pr in (('owner/repo/extra', 1), ('owner/repo?x', 1), ('owner/repo', 0)):
                with self.subTest(repo=repo, pr=pr), self.assertRaises(h.Broken):
                    h.cmd_fetch(SimpleNamespace(repo=repo, pr=pr, out=str(self.dest)))
            call.assert_not_called()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'input.json'

    def run_analyze(self, *extra):
        return subprocess.run([sys.executable, '-B', str(HERE / 'round_history.py'), 'analyze',
                               '--comments', str(self.path), '--reviewer', REVIEWER, *extra],
                              capture_output=True, text=True, encoding='utf-8')

    def test_missing_invalid_json_and_invalid_shapes_return_exit_two(self):
        payloads = (None, b'{bad', b'42', b'{}', b'[null]', b'[{"body": 1}]',
                    b'[{"body":"text"}]', b'[{"body":"text","created":"2026-10-16"}]')
        for payload in payloads:
            with self.subTest(payload=payload):
                if payload is not None:
                    self.path.write_bytes(payload)
                result = self.run_analyze()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('error:', result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_bad_threshold_is_a_cli_error(self):
        self.path.write_text('[]')
        result = self.run_analyze('--threshold', 'nan')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('Traceback', result.stderr)

    def test_legacy_snapshot_is_labelled_unknown_coverage(self):
        self.path.write_text(json.dumps([verdict()]), encoding='utf-8')
        result = self.run_analyze()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['collection']['pagination'], 'unknown')
        self.assertEqual(json.loads(result.stdout)['reviewer_signatures'], [h.signer_key(REVIEWER)])

    def test_fetch_snapshot_metadata_is_reported(self):
        self.path.write_text(json.dumps({'schema_version': 1, 'coverage': 'issue_comments_only',
                                         'pagination': 'all_pages_retrieved', 'comments': []}))
        result = self.run_analyze()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['collection']['coverage'], 'issue_comments_only')

    def test_fetch_executable_output_file_and_encoding_errors_are_concise(self):
        argv = ['fetch', '--repo', 'fictional/project', '--pr', '1', '--out', str(self.path)]
        for exc in (FileNotFoundError('gh unavailable'), PermissionError('output denied'),
                    UnicodeError('invalid response encoding')):
            with patch.object(h.subprocess, 'run', side_effect=exc), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(h.main(argv), 2)
                self.assertNotIn('Traceback', err.getvalue())
        response = SimpleNamespace(returncode=0, stdout='[[]]', stderr='')
        self.path.mkdir()
        with patch.object(h.subprocess, 'run', return_value=response), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(h.main(argv), 2)

    def test_invalid_json_transport_is_a_concise_error(self):
        response = SimpleNamespace(returncode=0, stdout='{bad', stderr='')
        with patch.object(h.subprocess, 'run', return_value=response), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(h.main(['fetch', '--repo', 'fictional/project', '--pr', '1', '--out', str(self.path)]), 2)
            self.assertNotIn('Traceback', err.getvalue())


class HistoricalSnapshotTests(unittest.TestCase):
    def test_original_snapshots_describe_events_without_inventing_rounds(self):
        for pr, count, approval in ((35, 3, None), (38, 5, 5)):
            comments = json.loads((HERE / f'fixtures/pr{pr}.json').read_text(encoding='utf-8'))
            r = h.report(h.extract_events(comments, ['Codex · PR review']))
            self.assertEqual(r['verdict_events'], count)
            self.assertEqual(r['first_approval_event_index'], approval)
            self.assertIsNone(r['review_rounds'])


if __name__ == '__main__':
    unittest.main()
