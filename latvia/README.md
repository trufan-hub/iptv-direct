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
