// ============================================================================
//  EuroScout — AI summary proxy (Cloudflare Worker)
//
//  The scouting-report "AI summary" button POSTs your bullet notes here.
//  This worker holds your Anthropic API key as a SECRET (never on any device),
//  calls Claude, and returns the summary. So your PC, iPad and phone all work
//  with nothing to paste anywhere.
//
//  SETUP (one time, ~5 min) — see SETUP.txt in this folder.
// ============================================================================

// Only these sites may call the worker (stops strangers from spending your key).
// Add/remove origins as needed. localhost lines let you test locally.
const ALLOWED_ORIGINS = [
  "https://turkmarkoo.github.io",
  "http://localhost:8000",
  "http://127.0.0.1:5500",
];

// Model. Cheaper/faster alternative: "claude-haiku-4-5-20251001"
const MODEL = "claude-sonnet-5";

// The scouting voice. Tweak this whenever you want — just redeploy the worker.
const SYSTEM_PROMPT =
  "You turn a professional basketball scout's shorthand bullet notes into a clean, " +
  "readable scouting summary. Write flowing prose, 2\u20134 short paragraphs. Use the " +
  "scout's OWN words, terminology and judgements \u2014 do not add observations, statistics, " +
  "comparisons or opinions they did not write, and never soften, hedge or inflate their " +
  "verdict. Keep it tight and direct, the way a scout talks. Output only the summary: " +
  "no preamble, no headings, no bullet points.";

function corsHeaders(origin) {
  const allowed = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...headers, "content-type": "application/json" },
  });
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const headers = corsHeaders(origin);

    // CORS preflight
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers });
    if (request.method !== "POST") return json({ error: "POST only" }, 405, headers);

    // Origin gate
    if (origin && !ALLOWED_ORIGINS.includes(origin))
      return json({ error: "Origin not allowed" }, 403, headers);

    if (!env.ANTHROPIC_API_KEY)
      return json({ error: "Worker missing ANTHROPIC_API_KEY secret" }, 500, headers);

    let body;
    try { body = await request.json(); }
    catch (e) { return json({ error: "Bad JSON" }, 400, headers); }

    const notes = String(body.notes || "").slice(0, 8000);
    if (!notes.trim()) return json({ error: "No notes" }, 400, headers);

    const player = String(body.player || "").slice(0, 120);
    const grade = body.grade ? `\u2014 scout's grade ${body.grade}/5` : "";
    const userMsg = `Player: ${player} ${grade}\n\nMy bullet notes:\n\n${notes}`;

    let apiResp;
    try {
      apiResp = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": env.ANTHROPIC_API_KEY,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify({
          model: MODEL,
          max_tokens: 800,
          system: SYSTEM_PROMPT,
          messages: [{ role: "user", content: userMsg }],
        }),
      });
    } catch (e) {
      return json({ error: "Could not reach Anthropic: " + e.message }, 502, headers);
    }

    const data = await apiResp.json().catch(() => null);
    if (!data) return json({ error: "Bad response from Anthropic (" + apiResp.status + ")" }, 502, headers);
    if (data.error) return json({ error: data.error.message || "API error" }, 502, headers);

    const summary = (data.content || [])
      .filter((b) => b.type === "text")
      .map((b) => b.text)
      .join("\n")
      .trim();

    return json({ summary }, 200, headers);
  },
};
