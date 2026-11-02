import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from codex_quota import LogUsage
from ccquota import parse_codex_limits


def event(stamp, total):
    return (json.dumps({'type': 'event_msg', 'timestamp': stamp.isoformat(),
                        'payload': {'type': 'token_count', 'info': {
                            'total_token_usage': {'total_tokens': total}}}}) + '\n').encode()


class UsageTests(unittest.TestCase):
    def test_incremental_repeats_partial_and_counter_reset(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            folder = Path(directory)/'sessions'
            folder.mkdir()
            path = folder/'a.jsonl'
            now = datetime.now().astimezone().replace(hour=12)
            yesterday = now - timedelta(days=1)
            path.write_bytes(event(yesterday, 100) + event(now, 150) + event(now, 150))
            reader = LogUsage(directory)
            self.assertEqual(reader.scan(now.timestamp())['today_tokens'], 50)
            self.assertEqual(reader.scan(now.timestamp())['today_tokens'], 50)
            pending = event(now, 180)
            with path.open('ab') as f:
                f.write(pending[:-1])
            self.assertEqual(reader.scan(now.timestamp())['today_tokens'], 50)
            with path.open('ab') as f:
                f.write(b'\n' + event(now, 20))
            self.assertEqual(reader.scan(now.timestamp())['today_tokens'], 100)

    def test_truncation_rebuild_and_midnight(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            folder = Path(directory)/'sessions'
            folder.mkdir()
            path = folder/'a.jsonl'
            now = datetime.now().astimezone().replace(hour=12)
            path.write_bytes(event(now, 1000) + event(now, 1200))
            reader = LogUsage(directory)
            self.assertEqual(reader.scan(now.timestamp())['today_tokens'], 1200)
            path.write_bytes(event(now, 30))
            self.assertEqual(reader.scan(now.timestamp())['today_tokens'], 30)
            self.assertEqual(reader.scan((now+timedelta(days=1)).timestamp())['today_tokens'], 0)

    def test_log_quota_expiry(self):
        limits = {'primary': {'used_percent': 40, 'window_minutes': 300, 'resets_at': 100}}
        self.assertIsNone(parse_codex_limits({'rateLimits': limits}, 101, 'logs')['five_hour'])


if __name__ == '__main__':
    unittest.main()
