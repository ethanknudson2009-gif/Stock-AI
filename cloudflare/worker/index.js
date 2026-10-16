// Forwards every request (including Streamlit's websocket) to the current tunnel URL in env.TARGET,
// so the app has a stable, friendly address even though the tunnel's own address changes.
export default {
  async fetch(request, env) {
    const target = new URL(env.TARGET);
    const url = new URL(request.url);
    url.protocol = target.protocol;
    url.host = target.host;
    const forwarded = new Request(url.toString(), request);
    // Streamlit rejects websocket/POST requests whose Origin differs from its own host.
    if (forwarded.headers.has("Origin")) forwarded.headers.set("Origin", target.origin);
    return fetch(forwarded, { redirect: "manual" });
  },
};
