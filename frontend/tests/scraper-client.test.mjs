import assert from 'node:assert/strict';
import { afterEach, mock, test } from 'node:test';
import { runScraper } from '../src/lib/scraper-client.ts';

afterEach(() => mock.restoreAll());

const cases = {
  invalid_email: 'Enter a valid email address for the Google account you want to use.',
  invalid_datetime: 'Choose a valid start date and time.',
  account_mismatch: 'The Google account you authorized does not match the selected email. Run the scraper again and choose the matching account.',
  oauth_setup_required: 'Gmail setup is incomplete. Add your OAuth client file at backend/credentials.json, then try again.',
  authorization_failed: 'Could not authorize Gmail access. Run the scraper again and complete Google authorization.',
  search_running: 'A payment search is already running. Wait for it to finish, then try again.',
  invalid_request: 'Some search settings are invalid. Check the account, date, time, category, and payment sources.',
  search_failed: 'The search could not finish. Check the backend terminal for details, then try again.',
};

for (const [code, message] of Object.entries(cases)) {
  test(`shows the approved message for ${code}`, async () => {
    mock.method(globalThis, 'fetch', async () => Response.json(
      { detail: { code, message: 'private server details' } }, { status: 400 },
    ));
    await assert.rejects(runScraper({}), { message });
  });
}

test('unknown and malformed errors use the safe fallback', async () => {
  for (const detail of [{ code: 'unknown' }, { code: '__proto__' }, 'private-token', null]) {
    mock.method(globalThis, 'fetch', async () => Response.json({ detail }, { status: 500 }));
    await assert.rejects(runScraper({}), { message: cases.search_failed });
    mock.restoreAll();
  }
});

test('network failures explain how to reach the backend', async () => {
  mock.method(globalThis, 'fetch', async () => { throw new TypeError('fetch failed'); });
  await assert.rejects(runScraper({}), {
    message: 'Could not reach the backend. Make sure it is running at http://localhost:8000, then try again.',
  });
});

test('invalid JSON and malformed success data are unexpected responses', async () => {
  for (const response of [new Response('<html>Error</html>', { status: 502 }),
    Response.json(null), Response.json({ data: {} }),
    Response.json({ data: { new_count: -1, total_amount: 0 } }),
    Response.json({ data: { new_count: 1, total_amount: '25.00' } })]) {
    mock.method(globalThis, 'fetch', async () => response);
    await assert.rejects(runScraper({}), {
      message: 'The backend returned an unexpected response. Check the backend terminal for details.',
    });
    mock.restoreAll();
  }
});

test('posts settings and returns a valid success result', async () => {
  const result = { data: { new_count: 2, total_amount: 50 } };
  const fetch = mock.method(globalThis, 'fetch', async () => Response.json(result));
  assert.deepEqual(await runScraper({ category: 'dues' }), result);
  const [url, options] = fetch.mock.calls[0].arguments;
  assert.equal(url, 'http://localhost:8000/api/scraper/run');
  assert.equal(options.method, 'POST');
  assert.deepEqual(JSON.parse(options.body), { category: 'dues' });
});
