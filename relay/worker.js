// Cloudflare Worker: passes requests from GitHub on to the Fuel Finder API.
// Fuel Finder blocks requests from outside the UK; GitHub's machines are in the US.
// Only requests carrying the right X-Relay-Key are passed on.
export default {
  async fetch(request, env) {
    if (!env.RELAY_KEY || request.headers.get("X-Relay-Key") !== env.RELAY_KEY) {
      return new Response("Relay key missing or wrong", { status: 401 });
    }
    const url = new URL(request.url);
    const target = "https://www.fuel-finder.service.gov.uk" + url.pathname + url.search;

    // Pass on only the headers the API needs, so nothing else leaks through.
    const headers = new Headers();
    for (const name of ["authorization", "content-type", "accept"]) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }
    const init = { method: request.method, headers };
    if (request.method !== "GET" && request.method !== "HEAD") init.body = await request.text();

    const resp = await fetch(target, init);
    return new Response(resp.body, {
      status: resp.status,
      headers: { "content-type": resp.headers.get("content-type") || "application/json" },
    });
  },
};
