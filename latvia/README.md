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

All five returned HTTP 200 and valid HLS manifests on the GitHub server during the initial test (22.11.2026). This does not confirm playback from a specific Latvian television set.

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
