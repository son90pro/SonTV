import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

VN_TZ = timezone(timedelta(hours=7))

PROVIDERS_CONFIG = [
    {
        "id": "the-thao",
        "name": "Thể Thao",
        "sport": "football",
        "default_group": "Trực tiếp Thể Thao",
        "m3u_url": "https://raw.githubusercontent.com/son90pro/TV/refs/heads/main/TheThao_Full.m3u",
        "update_group_id": "the-thao-group-0",
        "update_channel_id": "the-thao-0",
    },
    {
        "id": "truyen-hinh",
        "name": "Truyền hình",
        "sport": "tv",
        "default_group": "Kênh Truyền Hình",
        "m3u_url": "https://raw.githubusercontent.com/son90pro/Giai-Tri-VIP/refs/heads/main/truyen_hinh.m3u",
        "update_group_id": None,
        "update_channel_id": None,
    },
]


def fetch_text(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return raw.decode("utf-8-sig", errors="replace")


def make_channel(
    ch_id: str,
    name: str,
    url: str,
    sport: str,
    subtitle: str,
    logo: str = "",
    headers: dict | None = None,
    manifest_type: str = "hls",
) -> dict:
    hdrs = headers or {}
    return {
        "id": ch_id,
        "name": name,
        "sport": sport,
        "is_live": True,
        "match_time": "",
        "subtitle": subtitle,
        "home_team": "",
        "away_team": "",
        "home_logo": logo,
        "away_logo": "",
        "labels": [],
        "sources": [
            {
                "name": "Link 1",
                "headers": hdrs,
                "contents": [
                    {
                        "streams": [
                            {
                                "name": "Link 1",
                                "manifest_type": manifest_type,
                                "headers": hdrs,
                                "drm": {"type": "", "license_key": ""},
                                "remote_data": {
                                    "url": url,
                                    "headers": hdrs,
                                    "manifest_type": manifest_type,
                                    "drm": {"type": "", "license_key": ""},
                                },
                            }
                        ]
                    }
                ],
            }
        ],
    }


def parse_m3u(content: str, default_group: str) -> list[dict]:
    items: list[dict] = []
    pending_extinf: str | None = None
    pending_headers: dict[str, str] = {}

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF:"):
            pending_extinf = line
            continue

        if line.startswith("#EXTVLCOPT:"):
            opt = line.split(":", 1)[1].strip()
            if "=" in opt:
                k, v = opt.split("=", 1)
                k = k.strip().lower()
                v = v.strip()
                if k == "http-user-agent":
                    pending_headers["User-Agent"] = v
                elif k == "http-referrer":
                    pending_headers["Referer"] = v
            continue

        if line.startswith("#"):
            continue

        if pending_extinf is not None:
            group_match = re.search(r'group-title="([^"]*)"', pending_extinf)
            logo_match = re.search(r'tvg-logo="([^"]*)"', pending_extinf)
            name = pending_extinf.split(",", 1)[1].strip() if "," in pending_extinf else "Kênh"

            group_name = (group_match.group(1).strip() if group_match else "") or default_group
            logo = logo_match.group(1).strip() if logo_match else ""

            stream_url = line
            headers = dict(pending_headers)
            if "|" in line:
                parts = line.split("|", 1)
                stream_url = parts[0].strip()
                for extra in parts[1].split("&"):
                    if "=" in extra:
                        hk, hv = extra.split("=", 1)
                        headers[hk.strip()] = hv.strip()

            manifest_type = "dash" if ".mpd" in stream_url.lower() else "hls"

            items.append(
                {
                    "name": name or "Kênh",
                    "group": group_name,
                    "logo": logo,
                    "url": stream_url,
                    "headers": headers,
                    "manifest_type": manifest_type,
                }
            )
            pending_extinf = None
            pending_headers = {}

    return items


def build_provider(cfg: dict, updated_str: str) -> dict:
    provider_id = cfg["id"]
    provider_name = cfg["name"]
    sport = cfg["sport"]
    default_group = cfg["default_group"]
    m3u_url = cfg["m3u_url"]

    crawl_status = "ok"
    crawl_error = ""
    parsed_items: list[dict] = []

    try:
        m3u_text = fetch_text(m3u_url)
        parsed_items = parse_m3u(m3u_text, default_group=default_group)
    except Exception as exc:
        crawl_status = "error"
        crawl_error = str(exc)

    grouped_channels: dict[str, list[dict]] = {}
    channel_counter = 1

    for entry in parsed_items:
        grp_name = entry["group"]
        ch_id = f"{provider_id}-{channel_counter}"
        channel_counter += 1

        ch_obj = make_channel(
            ch_id=ch_id,
            name=entry["name"],
            url=entry["url"],
            sport=sport,
            subtitle=grp_name,
            logo=entry["logo"],
            headers=entry["headers"],
            manifest_type=entry["manifest_type"],
        )
        grouped_channels.setdefault(grp_name, []).append(ch_obj)

    groups: list[dict] = []

    if cfg.get("update_group_id") and cfg.get("update_channel_id"):
        groups.append(
            {
                "id": cfg["update_group_id"],
                "name": "⏱️ Cập Nhật",
                "channels": [
                    make_channel(
                        ch_id=cfg["update_channel_id"],
                        name=f"Updated {updated_str}",
                        url="https://raw.githubusercontent.com/son90pro/SonTV/refs/heads/main/playlist.json",
                        sport=sport,
                        subtitle="⏱️ Cập Nhật",
                    )
                ],
            }
        )

    for idx, (grp_name, ch_list) in enumerate(grouped_channels.items()):
        groups.append(
            {
                "id": f"{provider_id}-group-{idx + 1}",
                "name": grp_name,
                "channels": ch_list,
            }
        )

    return {
        "id": provider_id,
        "name": provider_name,
        "crawl_status": crawl_status,
        "crawl_error": crawl_error,
        "groups": groups,
    }


def main() -> None:
    now_vn = datetime.now(VN_TZ)
    updated_str = now_vn.strftime("%d/%m %H:%M")

    providers = [build_provider(cfg, updated_str) for cfg in PROVIDERS_CONFIG]

    playlist = {
        "updated_at": now_vn.isoformat(),
        "providers": providers,
    }

    out_path = Path("playlist.json")
    out_path.write_text(json.dumps(playlist, ensure_ascii=False, indent=2), encoding="utf-8")

    for p in providers:
        total_ch = sum(len(g.get("channels", [])) for g in p.get("groups", []))
        print(f"[{p['id']}] status={p['crawl_status']} groups={len(p['groups'])} channels={total_ch}")


if __name__ == "__main__":
    main()
    
