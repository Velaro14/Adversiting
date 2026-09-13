#!/usr/bin/env python3
"""Merge qy-Ads-Rule and AdAway into native client rule-set formats.

qy-Ads-Rule is ABP-style and mostly carries suffix/wildcard semantics.
AdAway is a hosts file, so its hostnames are preserved as exact-domain rules.
Unsafe ABP path/modifier rules are never widened into whole-domain blocks.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

QY_UPSTREAM = "https://raw.githubusercontent.com/rssvcn/qy-Ads-Rule/main/black.txt"
ADAWAY_UPSTREAM = "https://adaway.org/hosts.txt"
ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rules"
UPSTREAM_DIR = ROOT / "upstream"
META = ROOT / "metadata.json"

HOST_RE = re.compile(r"^[a-z0-9._*?-]+$", re.I)
LABEL_RE = re.compile(r"^[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?$", re.I)
LOCAL_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "local",
    "broadcasthost",
    "ip6-localhost",
    "ip6-loopback",
    "ip6-allnodes",
    "ip6-allrouters",
}


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Adversiting-rule-sync/2.0"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8-sig")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def wildcard_regex(pattern: str) -> str:
    escaped = re.escape(pattern)
    escaped = escaped.replace(r"\*", ".*").replace(r"\?", ".")
    return f"^{escaped}$"


def loon_url_regex(pattern: str) -> str:
    """Compensate an ABP host wildcard at Loon's HTTP(S) URL layer."""
    escaped = re.escape(pattern)
    escaped = escaped.replace(r"\*", r"[^/:?#]*").replace(r"\?", r"[^/:?#]")
    return rf"^https?://(?:[^/:?#]*\.)?{escaped}(?::\d+)?(?:[/#?]|$)"


def parse_qy(text: str):
    suffixes: set[str] = set()
    keywords: set[str] = set()
    wildcards: set[str] = set()
    ports: dict[str, set[str]] = defaultdict(set)
    unsupported: list[tuple[str, str]] = []
    headers: dict[str, str] = {}

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("!"):
            m = re.match(r"!\s*([^:]+):\s*(.+)$", line)
            if m:
                headers[m.group(1).strip().lower()] = m.group(2).strip()
            continue
        if line.startswith("#"):
            continue
        if line.startswith("@@"):
            unsupported.append((line, "ABP exception rule is not emitted into a blocking ruleset"))
            continue
        if not line.startswith("||"):
            unsupported.append((line, "unsupported ABP rule type"))
            continue

        core, sep, modifiers = line.partition("$")
        if sep:
            unsupported.append((line, f"ABP modifier not safely portable: ${modifiers}"))
            continue

        body = core[2:]
        if body.endswith("^"):
            body = body[:-1]
        if "/" in body:
            unsupported.append((line, "URL/path-specific ABP rule cannot be represented safely by all routing clients"))
            continue

        host = body
        port = None
        if ":" in host:
            candidate, maybe_port = host.rsplit(":", 1)
            if maybe_port.isdigit() and 1 <= int(maybe_port) <= 65535:
                host, port = candidate, maybe_port
            else:
                unsupported.append((line, "non-standard host/port expression"))
                continue

        host = host.lower().rstrip(".")
        if not host or not HOST_RE.fullmatch(host):
            unsupported.append((line, "invalid or unsupported hostname pattern"))
            continue

        if "*" not in host and "?" not in host:
            kind, value = "suffix", host
        elif host.startswith("*.") and "*" not in host[2:] and "?" not in host[2:]:
            kind, value = "suffix", host[2:]
        elif re.fullmatch(r"\*[a-z0-9_-]+\*", host, re.I):
            kind, value = "keyword", host.strip("*")
        else:
            kind, value = "wildcard", host

        if port:
            if kind == "suffix":
                ports[port].add(value)
            else:
                unsupported.append((line, "wildcard/keyword combined with destination port is not portable"))
            continue

        if kind == "suffix":
            suffixes.add(value)
        elif kind == "keyword":
            keywords.add(value)
        else:
            wildcards.add(value)

    return headers, sorted(suffixes), sorted(keywords), sorted(wildcards), ports, unsupported


def valid_exact_host(host: str) -> bool:
    if not host or host in LOCAL_HOSTS or "." not in host or len(host) > 253:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    labels = host.split(".")
    return all(label and len(label) <= 63 and LABEL_RE.fullmatch(label) for label in labels)


def parse_adaway(text: str) -> tuple[list[str], int]:
    domains: set[str] = set()
    skipped = 0
    sinkholes = {"127.0.0.1", "0.0.0.0", "::1"}

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2 or parts[0] not in sinkholes:
            skipped += 1
            continue
        for item in parts[1:]:
            host = item.lower().rstrip(".")
            if valid_exact_host(host):
                domains.add(host)
            elif host not in LOCAL_HOSTS:
                skipped += 1

    return sorted(domains), skipped


def covered_by_suffix(domain: str, suffixes: set[str]) -> bool:
    labels = domain.split(".")
    for i in range(len(labels) - 1):
        if ".".join(labels[i:]) in suffixes:
            return True
    return domain in suffixes


def header_lines(prefix: str, headers: dict[str, str], qy_hash: str, adaway_hash: str) -> list[str]:
    return [
        f"{prefix} Title: Merged advertising blocklist",
        f"{prefix} qy-Ads-Rule Version: {headers.get('version', 'unknown')}",
        f"{prefix} Source-1: {QY_UPSTREAM}",
        f"{prefix} Source-1-SHA256: {qy_hash}",
        f"{prefix} Source-2: {ADAWAY_UPSTREAM}",
        f"{prefix} Source-2-SHA256: {adaway_hash}",
        f"{prefix} Generated by scripts/convert_rules.py",
        "",
    ]


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def build_outputs(headers, exacts, suffixes, keywords, wildcards, ports, unsupported, qy_hash, adaway_hash):
    RULES.mkdir(parents=True, exist_ok=True)
    UPSTREAM_DIR.mkdir(parents=True, exist_ok=True)

    loon = header_lines("#", headers, qy_hash, adaway_hash)
    loon += [
        "# AdAway hosts are emitted as DOMAIN exact matches.",
        "# Wildcard note: Loon has no domain-level wildcard rule.",
        "# URL-REGEX compensates qy wildcard rules for HTTP/HTTPS only.",
        "",
    ]
    loon += [f"DOMAIN,{d}" for d in exacts]
    loon += [f"DOMAIN-SUFFIX,{d}" for d in suffixes]
    loon += [f"DOMAIN-KEYWORD,{k}" for k in keywords]
    loon += [f"URL-REGEX,{loon_url_regex(w)}" for w in wildcards]
    for port in sorted(ports, key=int):
        loon += [f"AND,((DOMAIN-SUFFIX,{d}),(DEST-PORT,{port}))" for d in sorted(ports[port])]
    write_text(RULES / "Loon.list", "\n".join(loon))

    surge = header_lines("#", headers, qy_hash, adaway_hash)
    surge += [f"DOMAIN,{d}" for d in exacts]
    surge += [f"DOMAIN-SUFFIX,{d}" for d in suffixes]
    surge += [f"DOMAIN-KEYWORD,{k}" for k in keywords]
    surge += [f"DOMAIN-WILDCARD,{w}" for w in wildcards]
    for port in sorted(ports, key=int):
        surge += [f"AND,((DOMAIN-SUFFIX,{d}),(DEST-PORT,{port}))" for d in sorted(ports[port])]
    write_text(RULES / "Surge.list", "\n".join(surge))

    quanx = header_lines("#", headers, qy_hash, adaway_hash)
    quanx += [f"host, {d}, reject" for d in exacts]
    quanx += [f"host-suffix, {d}, reject" for d in suffixes]
    quanx += [f"host-keyword, {k}, reject" for k in keywords]
    quanx += [f"host-wildcard, {w}, reject" for w in wildcards]
    write_text(RULES / "QuanX.list", "\n".join(quanx))

    clash_payload = [f"DOMAIN,{d}" for d in exacts]
    clash_payload += [f"DOMAIN-SUFFIX,{d}" for d in suffixes]
    clash_payload += [f"DOMAIN-KEYWORD,{k}" for k in keywords]
    clash_payload += [f"DOMAIN-WILDCARD,{w}" for w in wildcards]
    for port in sorted(ports, key=int):
        clash_payload += [f"AND,((DOMAIN-SUFFIX,{d}),(DST-PORT,{port}))" for d in sorted(ports[port])]
    clash = [
        "# Mihomo / Clash.Meta classical rule-provider",
        "# Requires modern Mihomo rule syntax; legacy Dreamacro Clash is not targeted.",
        f"# Source-1: {QY_UPSTREAM}",
        f"# Source-2: {ADAWAY_UPSTREAM}",
        "payload:",
    ]
    clash += ["  - " + json.dumps(item, ensure_ascii=False) for item in clash_payload]
    write_text(RULES / "Clash.yaml", "\n".join(clash))

    sb_rule: dict[str, object] = {}
    if exacts:
        sb_rule["domain"] = exacts
    if suffixes:
        sb_rule["domain_suffix"] = suffixes
    if keywords:
        sb_rule["domain_keyword"] = keywords
    if wildcards:
        sb_rule["domain_regex"] = [wildcard_regex(w) for w in wildcards]
    sb_rules: list[dict[str, object]] = [sb_rule] if sb_rule else []
    for port in sorted(ports, key=int):
        sb_rules.append({"domain_suffix": sorted(ports[port]), "port": [int(port)]})
    write_text(RULES / "SingBox.json", json.dumps({"version": 3, "rules": sb_rules}, ensure_ascii=False, indent=2))

    xray_domains = [f"full:{d}" for d in exacts]
    xray_domains += [f"domain:{d}" for d in suffixes]
    xray_domains += [f"keyword:{k}" for k in keywords]
    xray_domains += [f"regexp:{wildcard_regex(w)}" for w in wildcards]
    xray_rules: list[dict[str, object]] = []
    if xray_domains:
        xray_rules.append({"domain": xray_domains, "outboundTag": "block"})
    for port in sorted(ports, key=int):
        xray_rules.append({
            "domain": [f"domain:{d}" for d in sorted(ports[port])],
            "port": int(port),
            "outboundTag": "block",
        })
    write_text(RULES / "Xray.json", json.dumps({"routing": {"domainStrategy": "AsIs", "rules": xray_rules}}, ensure_ascii=False, indent=2))

    unsupported_lines = header_lines("#", headers, qy_hash, adaway_hash)
    unsupported_lines += ["# qy-Ads-Rule entries below were intentionally not widened into domain blocks.", ""]
    for raw, reason in unsupported:
        unsupported_lines += [f"# {reason}", raw, ""]
    write_text(RULES / "unsupported.txt", "\n".join(unsupported_lines))


def main() -> int:
    qy_text = fetch_url(QY_UPSTREAM)
    adaway_text = fetch_url(ADAWAY_UPSTREAM)
    qy_hash = sha256_text(qy_text)
    adaway_hash = sha256_text(adaway_text)
    converter_hash = sha256_text(Path(__file__).read_text(encoding="utf-8"))

    previous = {}
    if META.exists():
        try:
            previous = json.loads(META.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            previous = {}

    previous_sources = previous.get("sources", {})
    if (
        previous_sources.get("qy_ads_rule", {}).get("sha256") == qy_hash
        and previous_sources.get("adaway", {}).get("sha256") == adaway_hash
        and previous.get("converter_sha256") == converter_hash
    ):
        print("No upstream or converter change; nothing to update.")
        return 0

    headers, suffixes, keywords, wildcards, ports, unsupported = parse_qy(qy_text)
    adaway_domains, adaway_skipped = parse_adaway(adaway_text)

    suffix_set = set(suffixes)
    shadowed = sorted(d for d in adaway_domains if covered_by_suffix(d, suffix_set))
    exacts = sorted(set(adaway_domains) - set(shadowed))

    write_text(UPSTREAM_DIR / "black.txt", qy_text)
    write_text(UPSTREAM_DIR / "adaway-hosts.txt", adaway_text)
    build_outputs(headers, exacts, suffixes, keywords, wildcards, ports, unsupported, qy_hash, adaway_hash)

    port_count = sum(len(v) for v in ports.values())
    portable_total = len(exacts) + len(suffixes) + len(keywords) + len(wildcards) + port_count
    meta = {
        "sources": {
            "qy_ads_rule": {
                "url": QY_UPSTREAM,
                "title": headers.get("title"),
                "version": headers.get("version"),
                "sha256": qy_hash,
                "parsed": {
                    "domain_suffix": len(suffixes),
                    "domain_keyword": len(keywords),
                    "domain_wildcard": len(wildcards),
                    "port_specific": port_count,
                    "unsupported": len(unsupported),
                },
            },
            "adaway": {
                "url": ADAWAY_UPSTREAM,
                "sha256": adaway_hash,
                "parsed_exact_domains": len(adaway_domains),
                "skipped_non_domain_entries": adaway_skipped,
                "shadowed_by_qy_suffix": len(shadowed),
            },
        },
        "combined_source_sha256": sha256_text(qy_hash + "\n" + adaway_hash),
        "converter_sha256": converter_hash,
        "last_sync_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": {
            "domain_exact": len(exacts),
            "domain_suffix": len(suffixes),
            "domain_keyword": len(keywords),
            "domain_wildcard": len(wildcards),
            "port_specific": port_count,
            "unsupported": len(unsupported),
            "portable_total": portable_total,
        },
        "coverage": {
            "surge_portable_exact": portable_total,
            "mihomo_portable_exact": portable_total,
            "singbox_portable_exact": portable_total,
            "xray_portable_exact": portable_total,
            "loon_domain_exact": len(exacts) + len(suffixes) + len(keywords) + port_count,
            "loon_http_compensated_wildcards": len(wildcards),
            "quanx_without_port": portable_total - port_count,
        },
    }
    write_text(META, json.dumps(meta, ensure_ascii=False, indent=2))
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
