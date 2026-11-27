import json
import re
import urllib.request

SOURCES = [
    {
        "id": "the-thao",
        "name": "Thể Thao",
        "sport": "football",
        "default_group": "Trực tiếp Thể Thao",
        "m3u_url": "https://raw.githubusercontent.com/son90pro/TV/refs/heads/main/TheThao_Full.m3u",
    },
    {
        "id": "truyen-hinh",
        "name": "Truyền hình",
        "sport": "tv",
        "default_group": "Kênh Truyền Hình",
        "m3u_url": "https://raw.githubusercontent.com/son90pro/Giai-Tri-VIP/refs/heads/main/truyen_hinh.m3u",
    },
]

MAX_BYTES = 12 * 1024 * 1024  # 12 MB theo giới hạn PlaylistParser


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse_m3u_to_groups(m3u_text: str, default_group: str, sport: str, prefix: str):
    groups_map = {}
    pending_name = None
    pending_group = default_group
    pending_logo = ""
    pending_headers = {}
    idx = 0

    for raw_line in m3u_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF:"):
            name_part = line.split(",", 1)[1].strip() if "," in line else "Kênh phát"
            pending_name = name_part or "Kênh phát"

            grp_match = re.search(r'group-title="([^"]*)"', line)
            pending_group = (
                grp_match.group(1).strip()
                if grp_match and grp_match.group(1).strip()
                else default_group
            )

            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            pending_logo = logo_match.group(1).strip() if logo_match else ""
            pending_headers = {}

        elif line.startswith("#EXTVLCOPT:http-referrer="):
            pending_headers["Referer"] = line.split("=", 1)[1].strip()
        elif line.startswith("#EXTVLCOPT:http-user-agent="):
            pending_headers["User-Agent"] = line.split("=", 1)[1].strip()
        elif line.startswith("#"):
            continue
        else:
            if "|" in line:
                parts = line.split("|")
                stream_url = parts[0].strip()
                for opt in parts[1:]:
                    if "=" in opt:
                        k, v = opt.split("=", 1)
                        pending_headers[k.strip()] = v.strip()
            else:
                stream_url = line

            if stream_url.startswith("http://") or stream_url.startswith("https://"):
                ch_name = pending_name or f"Kênh {idx + 1}"
                if pending_group not in groups_map:
                    groups_map[pending_group] = []

                channel_obj = {
                    "id": f"{prefix}-{idx}",
                    "name": ch_name,
                    "sport": sport,
                    "is_live": True,
                    "match_time": "",
                    "subtitle": pending_group,
                    "home_team": "",
                    "away_team": "",
                    "home_logo": pending_logo,
                    "away_logo": "",
                    "labels": [],
                    "sources": [
                        {
                            "name": "Link 1",
                            "headers": pending_headers,
                            "contents": [
                                {
                                    "streams": [
                                        {
                                            "name": "Link 1",
                                            "manifest_type": "hls",
                                            "headers": pending_headers,
                                            "drm": {"type": "", "license_key": ""},
                                            "remote_data": {
                                                "url": stream_url,
                                                "headers": pending_headers,
                                                "manifest_type": "hls",
                                                "drm": {"type": "", "license_key": ""},
                                            },
                                        }
                                    ]
                                }
                            ],
                        }
                    ],
                }
                groups_map[pending_group].append(channel_obj)
                idx += 1

            pending_name = None
            pending_group = default_group
            pending_logo = ""
            pending_headers = {}

    result_groups = []
    for g_idx, (g_name, channels) in enumerate(groups_map.items()):
        result_groups.append(
            {
                "id": f"{prefix}-group-{g_idx}",
                "name": g_name,
                "channels": channels,
            }
        )
    return result_groups


def main():
    providers = []
    for src in SOURCES:
        m3u_content = fetch_text(src["m3u_url"])
        groups = parse_m3u_to_groups(
            m3u_content,
            default_group=src["default_group"],
            sport=src["sport"],
            prefix=src["id"],
        )
        providers.append(
            {
                "id": src["id"],
                "name": src["name"],
                "crawl_status": "ok",
                "crawl_error": "",
                "groups": groups,
            }
        )

    output = {"providers": providers}
    # Dùng separators gọn để giảm dung lượng file JSON
    json_str = json.dumps(output, ensure_ascii=False, separators=(",", ":"))
    raw_bytes = json_str.encode("utf-8")

    if len(raw_bytes) > MAX_BYTES:
        raise ValueError(f"File JSON vượt quá 12 MB ({len(raw_bytes)} bytes)")

    with open("playlist.json", "wb") as f:
        f.write(raw_bytes)

    print(f"Đã tạo playlist.json thành công ({len(raw_bytes)} bytes)")


if __name__ == "__main__":
    main()
