# QuickLynx

Click-to-tune QO-100 spectrum viewer for [Lynx](https://github.com/G8YTZ/lynx-datv-receiver). Runs entirely in
your browser, on your own PC or Mac — nothing runs on the Lynx Pi itself.

Shows the live BATC/Goonhilly wideband spectrum feed. Click a signal, confirm the symbol rate, and Lynx tunes to
it — the same idea as BATC's own [QO-100 Live Tune](https://wiki.batc.org.uk/QO100_Live_Tune), but talking to
Lynx's own HTTP API directly instead of MiniTiouner's UDP control protocol.

## Status: prototype, WebSocket URL confirmed working

This has been built carefully against BATC's own published server source
([`eshail-ghy-wb-fft-airspy`](https://github.com/BritishAmateurTelevisionClub/eshail-ghy-wb-fft-airspy)) and
tested wherever it could be — the frequency-mapping math, the symbol-rate estimation, the local server, the JS
itself. The one thing that couldn't be verified without a live connection was the exact public WebSocket URL -
confirmed via live browser testing (2026-07-30): **`wss://eshail.batc.org.uk/wb/fft`**, proxied through nginx
rather than the internal server's own documented port (7681). Already set as the default in Settings.

## Requirements

- Python 3 (already installed on macOS; on Windows, grab it from [python.org](https://python.org) — tick "Add
  to PATH" during install)
- A modern browser (Chrome or Firefox recommended)
- Lynx running and reachable on your local network

## Running it

**macOS/Linux:**
```
./run.sh
```

**Windows:** double-click `run.bat`

Either opens `http://127.0.0.1:8765/quicklynx.html` in your default browser automatically. If it doesn't, open
that URL yourself.

## First-time setup

Click **⚙ Settings** and fill in:

- **Lynx host** — your receiver's IP and port, e.g. `192.168.0.50:8080`
- **LNB LO offset** — defaults to `9750000` kHz (standard Ku-band LNB), matching Lynx's own default. Adjust if
  your actual LNB drifts from nominal.
- **BATC spectrum feed URL** — pre-filled with the confirmed working address; only change this if BATC's own
  infrastructure changes in future

## Why local, not hosted

The BATC feed is secure (`wss://`), but Lynx's own API is plain `http://` on your local network. If this page
were served over HTTPS from a public domain, browsers would block its requests to Lynx entirely — that's mixed
content policy, not something to work around casually. Running locally sidesteps this: there's no secure origin
to protect against a local, plain-HTTP connection in the first place.

## How the frequency mapping works

BATC's server sends a live FFT of a 10MHz slice centred on 745MHz (the SDR's tuned IF, not the real satellite
frequency), trimmed to the middle 90% of a 1024-bin FFT — 921 bins per update, roughly 9.77kHz apart. Adding the
LNB LO offset converts each bin back to the real QO-100 downlink frequency. Verified end to end: the displayed
range works out to ~10490.5–10499.5 MHz, matching QO-100's known wideband transponder range almost exactly.

## Symbol rate

Estimated automatically from the live spectrum shape at the click point: finds the true peak near the click,
estimates the local noise floor, and measures the width where the signal's displayed amplitude drops to 50% of
its own peak (relative to the floor). Below that point a real receiver wouldn't lock anyway, so there's no
practical value in tracing a signal's full taper all the way down to the noise floor - Justin's own suggestion,
after two earlier, more elaborate threshold-based attempts both still misread real signals.

**Status: mechanism simplified, exact conversion factor not yet empirically calibrated.** Working through this
surfaced a real problem with how it had been tested up to this point: signal shapes were verified only against
synthetic test data modelling a raised-cosine taper as a straight *linear*-amplitude curve. But the feed's
actual displayed values are on a *logarithmic* (dB) scale - confirmed directly from BATC's own server source
([`main.c`](https://github.com/BritishAmateurTelevisionClub/eshail-ghy-wb-fft-airspy/blob/master/main.c)), which
converts FFT power to dB before ever building the value it sends. A raised-cosine spectrum looks meaningfully
different on a log scale than a linear one, so passing synthetic tests build on that mismatched model didn't
mean much for how the code would actually behave on the real feed - which is exactly what happened, twice.

The current width-to-symbol-rate conversion factor (in `estimateSymbolRateKsps()`, clearly marked as
`WIDTH_TO_SYMBOL_RATE_FACTOR`) is a reasoned starting point based on a genuine, standard property of
raised-cosine filters - not yet an empirically confirmed one. The diagnostic overlay described below is the
tool for getting a real calibration point: click the QO-100 beacon (independently confirmed fixed at 1500 kS/s,
10491.5 MHz, DVB-S2), read the measured width off the overlay, and that's a real, known-correct data point to
calibrate the factor against, rather than more guessing against synthetic data.

**Fixed a real, separate bug** (2026-07-30): the peak-finding step, meant only to tolerate a slightly imprecise
click, had been sharing the same wide search window (~1.5MHz) as the edge-walk step that measures a signal's
full width - a value that genuinely needs to be that wide, to fully measure a 1500+ kS/s signal. Conflating the
two meant that on a busy transponder, any stronger signal anywhere within that whole span would get snapped to
instead of the one actually clicked - exactly the reported symptom (the detected signal sitting well to the
right of the intended one). Split into two separate, correctly-scoped values: a tight window for finding the
true peak near the actual click, and a wide one, only used afterward, for measuring that signal's width.

Also checked directly against BATC's own server source whether symbol rate might be embedded in the feed itself
rather than needing to be derived at all. It isn't: the WebSocket message is confirmed to be nothing but a flat
array of FFT magnitude values, no metadata. The wb chat channel carries free-form, human/software-posted signal
reports, not a structured, reliable per-signal API.

### Diagnostic overlay

Every click draws directly on the spectrum: a white dot at the detected peak, a dashed grey line at the
estimated noise floor, a dashed amber line at the threshold used, and the two detected edges as vertical lines
(green = stopped at the threshold as expected; red = hit the search radius or array boundary without finding
one, a clear sign something's off). A text readout in the top-right corner shows the raw peak/floor/threshold
values and the raw estimate before snapping - added specifically so real behaviour on the real feed can be read
off and reported directly, rather than continuing to guess against synthetic data that turned out not to
represent it well.

Real, live signals will still be noisier than any synthetic test can fully replicate, so the estimate remains a
starting point, not a guarantee: it's always shown in the dropdown for you to check or override before
confirming the tune, never applied silently.

## Chat panel

BATC's own "chat-only" page (`eshail.batc.org.uk/wb/chat/`), embedded on the right via `server.py`'s own local
proxy at `/proxy/chat` - not a direct `<iframe src="https://eshail...">`.

Direct embedding was tried first, on the reasoning that BATC's own, already-working page would sidestep needing
to reimplement their Socket.IO-based chat protocol. Confirmed via live testing (2026-07-30) that BATC's server
blocks this outright - the page loads fine as its own tab, but appears blank when framed directly, matching
exactly how a server-side `X-Frame-Options`/CSP restriction behaves. That header specifically governs a page
being nested inside *another document* via `<iframe>` - it has no effect on a page being the top-level
destination of its own navigation, which is why native apps that show this chat (e.g. Quick Tune) aren't doing
anything unusual: they use an embedded browser control navigating directly to the page as its own content, not
nesting it inside a different one.

The proxy sidesteps this the same way, more simply: `server.py` fetches the chat page server-side and re-serves
it from `localhost` with a `<base href="https://eshail.batc.org.uk/wb/chat/">` tag injected, so every relative
URL in the page - stylesheets, scripts, and critically the page's own Socket.IO connection, if it's built
relatively - resolves against BATC's real site rather than the local proxy path. BATC's own `X-Frame-Options`
header is deliberately not forwarded, since this response now genuinely comes from `localhost`, which is the
whole point.

**Confirmed working end to end** (2026-07-30, live testing): the panel loads and the chat actually connects,
including the Socket.IO layer - not just the page rendering visually. The one piece that couldn't be verified
without reaching BATC's real server directly (whether the chat's own JavaScript builds its Socket.IO connection
URL in a way the `<base>` tag covers) turned out fine in practice, matching the expectation that most Socket.IO
clients take an explicit server URL as a JS argument rather than deriving it relatively.

## Files

- `quicklynx.html` — the entire app (HTML/CSS/JS, no build step, no external dependencies)
- `server.py` — local server and BATC chat proxy (Python standard library only)
- `run.sh` / `run.bat` — launchers

## Credits

Frequency-mapping approach and the symbol-rate reference-bar idea both come from Rob M0DTS's original
[QO-100 Live Tune](https://github.com/m0dts/QO-100-WB-Live-Tune). The spectrum feed itself is BATC & AMSAT-UK's,
hosted at Goonhilly Earth Station.
