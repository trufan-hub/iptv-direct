# TruFan Latvia IPTV

Separate, auto-updating Latvian television playlist. Existing `direct.m3u` and `rutube-auto` are not modified.

**M3U for Lazy IPTV Deluxe:**
https://trufan-hub.github.io/iptv-direct/latvia.m3u

**Dedicated XMLTV guide:**
https://trufan-hub.github.io/iptv-direct/latvia-guide.xml

**Diagnostics:**
https://trufan-hub.github.io/iptv-direct/latvia-report.json

## Channels in the initial verified set

- LTV1 — LSM Pasaule HLS
- LTV7 — LSM Pasaule HLS
- ReTV — confirmed HLS, two CDN candidates
- Radio SWH TV — confirmed HLS
- Vidusdaugavas Televīzija — confirmed HLS

All five returned HTTP 200 and valid HLS manifests on the GitHub server during the initial test (22.11.2026). **This confirms neither actual video nor geo-access. The user directly confirmed on 22.11.2026 that LTV7 `ltv7_pasaule` played a GEO-RESTRICTION SLATE, not the real television programme.** The official REplay.lv LTV7 stream did play correctly on the same user's phone in Latvia.

The EPG is generated from a Latvia-scoped XMLTV source and contains verified schedules for **four** channels. ReTV EPG remains unavailable in the inspected feed; the script does not invent schedule entries. Existing titles, descriptions, subtitles and genres are retained when provided.

**Important:** `ltv1_pasaule` and `ltv7_pasaule` are international/rights-filtered streams and may not show the full domestic Latvian programme, especially third-party films, sports or special programming. Compare with the official LSM player if a broadcast is missing.

## Update architecture

The workflow `.github/workflows/latvia-update.yml` independently checks HLS sources and updates M3U, XMLTV, logos and diagnostics every six hours. It is separate from the standard `Update IPTV Direct` workflow.

- `latvia/channels.json` — verified streams and fallback URLs with stable `lv.*` channel IDs
- `latvia/build.py` — HLS health checks and narrowed EPG XMLTV generator
- `latvia/check_release.py` — checks stream-count minimum, EPG validity and ID consistency
- `latvia/candidates.json` — non-verified or commercial channels, including 3+ (TV3 Plus), never automatically included in the published playlist
- `docs/latvia-logos.json` — preserved logo mappings
- `docs/latvia-report.json` — current availability and EPG coverage

The playlist has one `url-tvg` header pointing only to its own `latvia-guide.xml`. Each channel has a stable `tvg-id`. No external EPG is required in the television's player settings. If a feed or key validation fails, the workflow stops before publishing, retaining the previous working site.

**Rights:** the M3U links directly to provider HLS endpoints; it does not host video. The XMLTV data comes from a public third-party EPG service. Public availability does not by itself establish redistribution rights; review source terms before broader redistribution or commercial use. Commercial channels such as 3+, TV3 and TV6 are not included without authorised public streams.

## Confirmed domestic alternatives (22.11.2026)

- **Official REplay.lv**: https://replay.lsm.lv/lv/skaties/tiesraide/ltv7 and https://replay.lsm.lv/lv/skaties/tiesraide/ltv1 . User confirmed domestic LTV7 works in their phone browser. Official FAQ states Smart TV playback is through browser, not a native app: https://replay.lsm.lv/lv/skaties/buj . This is an HTML player, **not** a direct M3U.
- **Go3 Go free ad-supported TV package**: https://palidziba.go3.lv/article/kas-ir-go3-go-lv/ . Official list includes LTV1, LTV7, ReTV, SWH TV, TV3, TV6, TV24, TV4, EWTN Latvia and other local channels (subject to account eligibility); separate Go3 app, **not** exported IPTV streams; 3+ is NOT listed.
- **Free terrestrial DVB-T**: https://www.neplp.lv/lv/bezmaksas-programmas . Full domestic LTV1/LTV7 in SD and HD and several other channels, with antenna + DVB-T receiver. For local private LAN M3U, a supported tuner connected to Tvheadend can expose `http://[LOCAL_SERVER]:9981/playlist/channels.m3u` and `http://[LOCAL_SERVER]:9981/xmltv/channels`. This requires an always-on local server and hardware, and is not a public GitHub stream.
- Old `ltvlive3167.bstrm.net` CDN entries are currently unreachable in upstream HLS checks. The new REplay player uses Redge; no persistent license-free direct domestic HLS has been confirmed yet. **Never replace the playlist with untested candidate streams or confuse HTTP 200 with video.**


## Latvian proxy for GitHub Actions (optional until configured)

The standard GitHub-hosted runner is not located in Latvia. To make **outbound HTTP(S) requests of the Latvian IPTV builder** exit via Latvia, supply your own private **HTTP CONNECT proxy with an LV public IP**.

**One-time private setup (do not paste the password into this repository or an issue):**

1. Obtain a legitimate, stable Latvia-based HTTP CONNECT proxy. Avoid shared free proxy lists, which can expose requests and credentials.
2. In GitHub open `trufan-hub/iptv-direct` → Settings → Secrets and variables → Actions → New repository secret.
3. Name the secret exactly `LV_PROXY_URL`. Its value is a proxy address, for example `http://USERNAME:PASSWORD@LV_HOST:PORT`; substitute your actual credentials. URL-encode reserved characters in username and password.
4. Go to Actions → **Verify Latvia proxy and domestic LTV streams** → Run workflow. The script checks the proxy's observed egress country is `LV`, then requests the official LTV1/LTV7 playback API **through this proxy**. No credentials, full stream URLs or signed CDN tokens are printed.
5. Once configured, the existing **Update TruFan Latvia IPTV** workflow supplies `HTTPS_PROXY` and `HTTP_PROXY` only to its Latvia build step. The build first validates Latvian proxy egress and **fails closed** if the configured proxy is blocked or resolves to a non-LV country. Without the secret, the pre-existing direct workflow continues unchanged.

**This is not a streaming relay:** GitHub Pages still serves a static M3U which the TV opens directly; it does **not** pass TV video traffic through the Latvian proxy. The official Redge configuration may bind CDN access to the *proxy's IP*, whereas the TV uses its own IP, so a tokenised URL that works on GitHub might fail on the TV. Likewise the official API may still return the `*_pasaule` placeholder feed. Neither an HTTP 200 nor a `#EXTM3U` response guarantees playable domestic video. The separate proxy probe must show a domestic candidate before any LTV channel source is changed, followed by real playback verification on a device in Latvia.

For truly IP-bound streams, playback must originate from an authorised same-IP endpoint or be handled by the official player. Do not publish temporary signed URLs or proxy credentials to GitHub Pages.

This proxy configuration applies only to the Latvia build requests, **not** the entire GitHub checkout/deployment infrastructure, `direct.m3u` or `rutube-auto`.
