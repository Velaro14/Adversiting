#!/usr/bin/env python3
"""Merge qy-Ads-Rule and AdAway into native client rule-set formats.

Design goals:
- Preserve qy-Ads-Rule's ABP hostname semantics as closely as each client allows.
- Preserve AdAway hosts entries as exact hostname matches (never widen them to suffixes).
- Never widen path/modifier ABP rules into whole-domain blocks.
- Fail closed on suspiciously small or malformed upstream data.
- Rebuild outputs on every run so accidental output drift is repaired automatically.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import sys
import time
import urllib.error
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

HOST_RE = re.compile(r"^[a-z0-9._*-]+$", re.I)
LABEL_RE = re.compile(r"^[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?$", re.I)

MIN_QY_RECOGNIZED = 300
MIN_ADAWAY_DOMAINS = 1000

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


def fetch_url(url: str, attempts: int = 3) -> str:
    """Fetch text with bounded retries; raise instead of returning partial data."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Adversiting-rule-sync/3.0",
                    "Accept": "text/plain,*/*;q=0.1",
                },
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = resp.read()
            text = data.decode("utf-8-sig")
            if not text.strip():
                raise RuntimeError(f"empty response from {url}")
            return text
        except (urllib.error.URLError, TimeoutError, OSError, UnicodeError, RuntimeError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"failed to fetch {url} after {attempts} attempts: {last_error}")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def wildcard_fragment(pattern: str, star: str = ".*") -> str:
    """Escape a hostname pattern and expand ABP '*' (ABP '?' is not a wildcard)."""
    escaped = re.escape(pattern)
    return escaped.replace(r"\*", star)


def abp_host_regex(pattern: str) -> str:
    """Project an ABP ||host-pattern^ rule onto hostname matching.

    The optional label prefix preserves the || domain-anchor behavior: a fixed
    pattern such as ad-*.example.com also matches x.ad-foo.example.com.
    ABP network filters are case-insensitive unless $match-case is present;
    qy-Ads-Rule has no such modifier on the portable wildcard entries.
    """
    return rf"(?i)^(?:[^.]+\.)*{wildcard_fragment(pattern)}$"


def loon_url_regex(pattern: str) -> str:
    """HTTP(S)-layer compensation for ABP wildcard hostname rules in Loon."""
    fragment = wildcard_fragment(pattern, r"[^/:?#]*")
    return rf"(?i)^https?://(?:[^/:?#.]+\.)*{fragment}(?::\d+)?(?:[/#?]|$)"


def wildcard_variants(pattern: str) -> list[str]:
    """Hostname wildcard variants for engines without hostname regex.

    ABP's || anchor may start at any domain-label boundary. A wildcard pattern
    with a fixed prefix therefore needs both the base form and a subdomain form.
    Leading-* patterns already cover that prefix space.
    """
    if pattern.startswith("*"):
        return [pattern]
    return [pattern, f"*.{pattern}"]


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

        # ABP '?' is a literal URL query separator, not a one-character wildcard.
        if any(ch in body for ch in ("/", "?", "#")):
            unsupported.append((line, "URL/path/query-specific ABP rule is not portable as a hostname rule"))
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

        if "*" not in host:
            kind, value = "suffix", host
        elif re.fullmatch(r"\*[a-z0-9_-]+\*", host, re.I):
            kind, value = "keyword", host.strip("*")
        else:
            # Keep leading '*.' as wildcard. Turning it into DOMAIN-SUFFIX would
            # incorrectly add the apex hostname, which ABP '*.example.com' does not.
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


def is_sinkhole_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_unspecified


def parse_adaway(text: str) -> tuple[list[str], int]:
    domains: set[str] = set()
    skipped = 0

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2 or not is_sinkhole_ip(parts[0]):
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
    return any(".".join(labels[i:]) in suffixes for i in range(len(labels)))


def validate_upstreams(
    headers: dict[str, str],
    suffixes: list[str],
    keywords: list[str],
    wildcards: list[str],
    ports: dict[str, set[str]],
    unsupported: list[tuple[str, str]],
    adaway_domains: list[str],
) -> None:
    qy_recognized = (
        len(suffixes)
        + len(keywords)
        + len(wildcards)
        + sum(len(v) for v in ports.values())
        + len(unsupported)
    )
    if qy_recognized < MIN_QY_RECOGNIZED:
        raise RuntimeError(
            f"qy-Ads-Rule parse looks suspicious: only {qy_recognized} recognized entries"
        )
    if headers.get("title") != "晴雅广告拦截规则":
        raise RuntimeError(f"unexpected qy-Ads-Rule title: {headers.get('title')!r}")
    if len(adaway_domains) < MIN_ADAWAY_DOMAINS:
        raise RuntimeError(
            f"AdAway parse looks suspicious: only {len(adaway_domains)} exact domains"
        )
    if any("*" in d for d in suffixes):
        raise AssertionError("wildcard leaked into suffix rules")


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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def build_outputs(
    headers,
    exacts,
    suffixes,
    keywords,
    wildcards,
    ports,
    unsupported,
    qy_hash,
    adaway_hash,
) -> None:
    RULES.mkdir(parents=True, exist_ok=True)
    UPSTREAM_DIR.mkdir(parents=True, exist_ok=True)

    # Loon: exact/suffix/keyword/port rules are native. Loon does not expose a
    # hostname-level wildcard/regex type, so wildcard rules receive HTTP(S)
    # URL-REGEX compensation. HTTPS full-URL matching may require MITM.
    loon = header_lines("#", headers, qy_hash, adaway_hash)
    loon += [
        "# AdAway hosts are emitted as DOMAIN exact matches.",
        "# qy wildcard rules use URL-REGEX as HTTP(S)-layer compensation.",
        "# This is not equivalent to hostname-layer matching for opaque TCP/UDP.",
        "",
    ]
    loon += [f"DOMAIN,{d}" for d in exacts]
    loon += [f"DOMAIN-SUFFIX,{d}" for d in suffixes]
    loon += [f"DOMAIN-KEYWORD,{k}" for k in keywords]
    loon += [f"URL-REGEX,{loon_url_regex(w)}" for w in wildcards]
    for port in sorted(ports, key=int):
        loon += [
            f"AND,((DOMAIN-SUFFIX,{d}),(DEST-PORT,{port}))"
            for d in sorted(ports[port])
        ]
    write_text(RULES / "Loon.list", "\n".join(loon))

    # Surge DOMAIN-WILDCARD '*' crosses dots. Fixed-prefix ABP patterns need a
    # second '*.pattern' form to preserve || matching from a subdomain boundary.
    surge = header_lines("#", headers, qy_hash, adaway_hash)
    surge += [f"DOMAIN,{d}" for d in exacts]
    surge += [f"DOMAIN-SUFFIX,{d}" for d in suffixes]
    surge += [f"DOMAIN-KEYWORD,{k}" for k in keywords]
    for w in wildcards:
        surge += [f"DOMAIN-WILDCARD,{v}" for v in wildcard_variants(w)]
    for port in sorted(ports, key=int):
        surge += [
            f"AND,((DOMAIN-SUFFIX,{d}),(DEST-PORT,{port}))"
            for d in sorted(ports[port])
        ]
    write_text(RULES / "Surge.list", "\n".join(surge))

    # Quantumult X has host-wildcard but no documented host+destination-port
    # logical conjunction. Port-specific qy rules are therefore not widened.
    quanx = header_lines("#", headers, qy_hash, adaway_hash)
    quanx += [f"host, {d}, reject" for d in exacts]
    quanx += [f"host-suffix, {d}, reject" for d in suffixes]
    quanx += [f"host-keyword, {k}, reject" for k in keywords]
    for w in wildcards:
        quanx += [f"host-wildcard, {v}, reject" for v in wildcard_variants(w)]
    write_text(RULES / "QuanX.list", "\n".join(quanx))

    # Mihomo supports DOMAIN-REGEX, so use it for a precise hostname projection
    # of ABP wildcard rules rather than relying on whole-host wildcard quirks.
    clash_payload = [f"DOMAIN,{d}" for d in exacts]
    clash_payload += [f"DOMAIN-SUFFIX,{d}" for d in suffixes]
    clash_payload += [f"DOMAIN-KEYWORD,{k}" for k in keywords]
    clash_payload += [f"DOMAIN-REGEX,{abp_host_regex(w)}" for w in wildcards]
    for port in sorted(ports, key=int):
        clash_payload += [
            f"AND,((DOMAIN-SUFFIX,{d}),(DST-PORT,{port}))"
            for d in sorted(ports[port])
        ]
    clash = [
        "# Mihomo / Clash.Meta classical rule-provider",
        "# Legacy Dreamacro Clash is intentionally not targeted.",
        f"# Source-1: {QY_UPSTREAM}",
        f"# Source-2: {ADAWAY_UPSTREAM}",
        "payload:",
    ]
    clash += ["  - " + json.dumps(item, ensure_ascii=False) for item in clash_payload]
    write_text(RULES / "Clash.yaml", "\n".join(clash))

    # sing-box groups domain match fields with OR semantics. Port is ANDed with
    # the domain group, which preserves the one qy host+port rule.
    sb_rule: dict[str, object] = {}
    if exacts:
        sb_rule["domain"] = exacts
    if suffixes:
        sb_rule["domain_suffix"] = suffixes
    if keywords:
        sb_rule["domain_keyword"] = keywords
    if wildcards:
        sb_rule["domain_regex"] = [abp_host_regex(w) for w in wildcards]
    sb_rules: list[dict[str, object]] = [sb_rule] if sb_rule else []
    for port in sorted(ports, key=int):
        sb_rules.append(
            {"domain_suffix": sorted(ports[port]), "port": [int(port)]}
        )
    write_text(
        RULES / "SingBox.json",
        json.dumps({"version": 3, "rules": sb_rules}, ensure_ascii=False, indent=2),
    )

    # Xray: full: is exact, domain: is apex-or-subdomain, keyword: is substring,
    # regexp: handles wildcard hostname projection. Multiple fields in one
    # RuleObject are ANDed, so port-specific rules remain separate RuleObjects.
    xray_domains = [f"full:{d}" for d in exacts]
    xray_domains += [f"domain:{d}" for d in suffixes]
    xray_domains += [f"keyword:{k}" for k in keywords]
    xray_domains += [f"regexp:{abp_host_regex(w)}" for w in wildcards]
    xray_rules: list[dict[str, object]] = []
    if xray_domains:
        xray_rules.append({"domain": xray_domains, "outboundTag": "block"})
    for port in sorted(ports, key=int):
        xray_rules.append(
            {
                "domain": [f"domain:{d}" for d in sorted(ports[port])],
                "port": int(port),
                "outboundTag": "block",
            }
        )
    write_text(
        RULES / "Xray.json",
        json.dumps(
            {"routing": {"domainStrategy": "AsIs", "rules": xray_rules}},
            ensure_ascii=False,
            indent=2,
        ),
    )

    unsupported_lines = header_lines("#", headers, qy_hash, adaway_hash)
    unsupported_lines += [
        "# qy-Ads-Rule entries below are intentionally not widened.",
        "# They require URL/app semantics unavailable across all target formats.",
        "",
    ]
    for raw, reason in unsupported:
        unsupported_lines += [f"# {reason}", raw, ""]
    write_text(RULES / "unsupported.txt", "\n".join(unsupported_lines))


def validate_written_outputs(
    exacts: list[str],
    suffixes: list[str],
    keywords: list[str],
    wildcards: list[str],
    ports: dict[str, set[str]],
) -> None:
    """Cheap structural checks that catch truncation or generator regressions."""
    portable = (
        len(exacts)
        + len(suffixes)
        + len(keywords)
        + len(wildcards)
        + sum(len(v) for v in ports.values())
    )

    singbox = json.loads((RULES / "SingBox.json").read_text(encoding="utf-8"))
    if singbox.get("version") != 3 or not singbox.get("rules"):
        raise RuntimeError("generated SingBox.json failed structural validation")

    xray = json.loads((RULES / "Xray.json").read_text(encoding="utf-8"))
    if not xray.get("routing", {}).get("rules"):
        raise RuntimeError("generated Xray.json failed structural validation")

    clash_text = (RULES / "Clash.yaml").read_text(encoding="utf-8")
    if clash_text.count("\n  - ") < portable:
        raise RuntimeError("generated Clash.yaml has fewer payload entries than expected")

    for name in ("Loon.list", "Surge.list", "QuanX.list"):
        text = (RULES / name).read_text(encoding="utf-8")
        if len(text.splitlines()) < len(exacts) + len(suffixes):
            raise RuntimeError(f"generated {name} looks truncated")


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

    headers, suffixes, keywords, wildcards, ports, unsupported = parse_qy(qy_text)
    adaway_domains, adaway_skipped = parse_adaway(adaway_text)
    validate_upstreams(
        headers,
        suffixes,
        keywords,
        wildcards,
        ports,
        unsupported,
        adaway_domains,
    )

    suffix_set = set(suffixes)
    shadowed = sorted(d for d in adaway_domains if covered_by_suffix(d, suffix_set))
    exacts = sorted(set(adaway_domains) - set(shadowed))

    previous_sources = previous.get("sources", {})
    basis_changed = not (
        previous_sources.get("qy_ads_rule", {}).get("sha256") == qy_hash
        and previous_sources.get("adaway", {}).get("sha256") == adaway_hash
        and previous.get("converter_sha256") == converter_hash
    )
    last_sync_utc = (
        datetime.now(timezone.utc).isoformat(timespec="seconds")
        if basis_changed or not previous.get("last_sync_utc")
        else previous["last_sync_utc"]
    )

    # Always rebuild. This repairs accidental edits/deletions even when the
    # upstream and converter hashes are unchanged; git diff decides whether a
    # commit is actually needed.
    write_text(UPSTREAM_DIR / "black.txt", qy_text)
    write_text(UPSTREAM_DIR / "adaway-hosts.txt", adaway_text)
    build_outputs(
        headers,
        exacts,
        suffixes,
        keywords,
        wildcards,
        ports,
        unsupported,
        qy_hash,
        adaway_hash,
    )
    validate_written_outputs(exacts, suffixes, keywords, wildcards, ports)

    port_count = sum(len(v) for v in ports.values())
    portable_total = (
        len(exacts) + len(suffixes) + len(keywords) + len(wildcards) + port_count
    )

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
        "last_sync_utc": last_sync_utc,
        "counts": {
            "domain_exact": len(exacts),
            "domain_suffix": len(suffixes),
            "domain_keyword": len(keywords),
            "domain_wildcard": len(wildcards),
            "port_specific": port_count,
            "unsupported": len(unsupported),
            "portable_hostname_rules": portable_total,
        },
        "coverage": {
            "surge_hostname_projection": portable_total,
            "mihomo_hostname_projection": portable_total,
            "singbox_hostname_projection": portable_total,
            "xray_hostname_projection": portable_total,
            "loon_native_hostname_and_port": len(exacts)
            + len(suffixes)
            + len(keywords)
            + port_count,
            "loon_http_compensated_wildcards": len(wildcards),
            "quanx_without_port": portable_total - port_count,
        },
        "semantics_note": (
            "ABP wildcard rules are projected onto hostname matching. Formal ABP "
            "wildcards can also span into URL text; layer-4 routing clients cannot "
            "represent that extra URL-path behavior without HTTP inspection."
        ),
    }
    write_text(META, json.dumps(meta, ensure_ascii=False, indent=2))
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
