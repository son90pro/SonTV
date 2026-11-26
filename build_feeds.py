import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

REPO_RAW_BASE = "https://raw.githubusercontent.com/son90pro/TV/refs/heads/main"


def fetch_text(source: str) -> str:
    """Đọc nội dung M3U từ URL hoặc file local."""
    if source.startswith(("http://", "https://")):
        req = Request(
            source,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        with urlopen(req, timeout=25) as resp:
            return resp.read().decode("utf-8", errors="replace")
    return Path(source).read_text(encoding="utf-8", errors="replace")


def parse_extinf_attr(line: str, attr: str) -> str:
    match = re.search(rf'{attr}="([^"]*)"', line)
    return match.group(1).strip() if match else ""


def parse_m3u_to_json(
    m3u_text: str,
    doc_id: str,
    doc_name: str,
    default_group: str = "Danh sách kênh",
    quality: str = "HD",
    server_name: str = "Server 1",
) -> dict:
    """Chuyển M3U sang cấu trúc JSON chuẩn của com.daotv.player."""
    grouped_channels = defaultdict(list)
    pending_meta = None

    for raw_line in m3u_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF:"):
            group_title = parse_extinf_attr(line, "group-title") or default_group
            tvg_name = parse_extinf_attr(line, "tvg-name")
            channel_name = line.split(",", 1)[1].strip() if "," in line else ""
            channel_name = channel_name or tvg_name or "Kênh chưa đặt tên"

            pending_meta = {
                "name": channel_name,
                "group": group_title,
            }
        elif not line.startswith("#") and pending_meta is not None:
            channel_obj = {
                "name": pending_meta["name"],
                "image": None,
                "labels": [],
                "sources": [
                    {
                        "name": "Nguồn 1",
                        "contents": [
                            {
                                "name": quality,
                                "streams": [
                                    {
                                        "name": server_name,
                                        "remote_data": None,
                                        "stream_links": [
                                            {
                                                "name": quality,
                                                "url": line,
                                                "default": True,
                                                "request_headers": [],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
            grouped_channels[pending_meta["group"]].append(channel_obj)
            pending_meta = None

    groups_list = [
        {"name": group_name, "channels": channels}
        for group_name, channels in grouped_channels.items()
        if channels
    ]

    return {
        "id": doc_id,
        "name": doc_name,
        "image": None,
        "groups": groups_list,
    }


def main():
    feeds = [
        {
            "id": "truyen-hinh",
            "name": "Truyền Hình",
            "tab_name": "TRUYỀN HÌNH",
            # Anh có thể đổi sang link raw M3U hoặc file .m3u trong repo
            "source": f"{REPO_RAW_BASE}/truyen_hinh.m3u",
            "out_file": "truyen_hinh.json",
            "raw_url": f"{REPO_RAW_BASE}/truyen_hinh.json",
            "default_group": "Truyền Hình",
        },
        {
            "id": "the-thao",
            "name": "Thể Thao",
            "tab_name": "THỂ THAO",
            "source": "https://tinyurl.com/SN-THTT-VIP",
            "out_file": "the_thao.json",
            "raw_url": f"{REPO_RAW_BASE}/the_thao.json",
            "default_group": "Thể Thao",
        },
    ]

    master_sources = []

    for item in feeds:
        try:
            m3u_text = fetch_text(item["source"])
            payload = parse_m3u_to_json(
                m3u_text=m3u_text,
                doc_id=item["id"],
                doc_name=item["name"],
                default_group=item["default_group"],
            )
            Path(item["out_file"]).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            master_sources.append({"name": item["tab_name"], "url": item["raw_url"]})
            print(f"[OK] {item['out_file']} -> {len(payload['groups'])} nhóm")
        except Exception as exc:
            print(f"[ERR] {item['tab_name']} ({item['source']}): {exc}")

    Path("Giaitri.json").write_text(
        json.dumps({"sources": master_sources}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("[OK] Giaitri.json updated")


if __name__ == "__main__":
    main()
