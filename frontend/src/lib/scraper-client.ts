const messages: Record<string, string> = {
  invalid_email: "Enter a valid email address for the Google account you want to use.",
  invalid_datetime: "Choose a valid start date and time.",
  account_mismatch: "The Google account you authorized does not match the selected email. Run the scraper again and choose the matching account.",
  oauth_setup_required: "Gmail setup is incomplete. Add your OAuth client file at backend/credentials.json, then try again.",
  authorization_failed: "Could not authorize Gmail access. Run the scraper again and complete Google authorization.",
  search_running: "A payment search is already running. Wait for it to finish, then try again.",
  invalid_request: "Some search settings are invalid. Check the account, date, time, category, and payment sources.",
  search_failed: "The search could not finish. Check the backend terminal for details, then try again.",
};

const unexpectedResponse = "The backend returned an unexpected response. Check the backend terminal for details.";

export async function runScraper(data: object) {
  let response: Response;
  try {
    response = await fetch("http://localhost:8000/api/scraper/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  } catch {
    throw new Error("Could not reach the backend. Make sure it is running at http://localhost:8000, then try again.");
  }

  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error(unexpectedResponse);
  }
  if (!response.ok) {
    const code = result?.detail?.code;
    throw new Error(typeof code === "string" && Object.hasOwn(messages, code)
      ? messages[code] : messages.search_failed);
  }
  if (!Number.isInteger(result?.data?.new_count) || result.data.new_count < 0
      || typeof result?.data?.total_amount !== "number" || !Number.isFinite(result.data.total_amount)) {
    throw new Error(unexpectedResponse);
  }
  return result as { data: { new_count: number; total_amount: number } };
}
