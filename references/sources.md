# Sources and caveats — source inventory (2026-11-01)

- NextTrace source and candidate Agent Skill/MCP integration: https://github.com/nxtrace/NTrace-core and https://github.com/nxtrace/NTrace-core/tree/main/skills/nexttrace
- mtr project & intermediate-hop ICMP rate limits: https://github.com/traviscross/mtr
- Trippy: https://github.com/fujiapple852/trippy
- Globalping API and CLI: https://globalping.io/cli ; https://github.com/jsdelivr/globalping/blob/master/public/v1/spec.yaml (quotas may change)
- RIPE Atlas well-known measurements and credits: https://atlas.ripe.net/docs/getting-started/well-known-measurements/ ; https://atlas.ripe.net/docs/getting-started/credits/
- RIPEstat Data API and commercial terms: https://stat.ripe.net/docs/data-api/ripestat-data-api ; https://stat.ripe.net/docs/getting-started/what-is-ripestat
- Cloudflare speed quality metrics: https://developers.cloudflare.com/speed/aim/
- Netflix FAST.com measurement scope: https://fast.com/zh/tw
- Ministry of Digital Affairs Taiwan submarine-cable fault notices: https://moda.gov.tw/major-policies/subseacable/fault/1749
- TeleGeography cable map (physical topology, not actual IP transit path): https://www.submarinecablemap.com/country/taiwan
- OCF Taiwan submarine cable community map and resilience tools: https://resilience.ocf.tw/ ; https://smc.peering.tw/
- Taiwan regulator NCC complaint process: https://api.ncc.gov.tw/chncc/app/artwebsite?id=450&module=artwebsite&serno=null
- NCC dispute resolution center: https://tcmc.tw/

**Do not infer** which physical submarine cable a packet traversed from traceroute, AS path, PTR hostnames, IP geolocation or a static map. CDN/anycast and local edge caches may keep traffic within Taiwan even when the service is internationally branded. Globalping probes measure their own path, not the return path from a service to a home subscriber.

**Before integrating or redistributing third-party components**: review each source's permitted usage, API terms and attribution. NextTrace is GPL-3.0, MTR GPL-2.0, and Trippy Apache-2.0; treating them as separately installed executables does not itself resolve all redistribution/licensing questions. The script uses only Python's standard library.

## Measurement definitions and maintenance references

- Python socket API (system `getaddrinfo`, socket timeout scope): https://docs.python.org/3/library/socket.html
- Python IP classification (`is_global` is not a substitute for unicast checks; classifications can change across versions): https://docs.python.org/3/library/ipaddress.html
- HTTP/1.1 status-line syntax: https://www.rfc-editor.org/rfc/rfc9112.html#section-4
- Informational versus final HTTP responses: https://www.rfc-editor.org/rfc/rfc9110.html#section-15
- Codex local Skill installation: https://developers.openai.com/codex/skills
- GitHub Actions official usage: https://github.com/actions/setup-python and https://github.com/actions/checkout

The list is an inventory, not an assertion that every external page, API, price,
license or incident is current. During this local review, the official Codex
Skill installation page and Actions usage examples were checked; no third-party
measurement API was invoked. Recheck a provider's current documentation before
adding its adapter. Existing links to cable notices are not evidence of an active
incident or of any user's traffic path.
