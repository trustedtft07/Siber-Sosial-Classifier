import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import requests

BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
MAX_SCRAPE_BYTES = 2 * 1024 * 1024


class ArticleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self.paragraphs: list[str] = []

        self._in_title = False
        self._in_p = False
        self._skip_tag = False
        self._skip_tags_stack: list[str] = []
        self._current_p: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag_lower = tag.lower()

        if tag_lower in {"script", "style", "nav", "footer", "header", "aside", "noscript"}:
            self._skip_tags_stack.append(tag_lower)
            self._skip_tag = True
            return

        if self._skip_tag:
            return

        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag_lower == "title" and not self.title:
            self._in_title = True
        elif tag_lower == "meta" and not self.description:
            prop = attr_dict.get("property", "").lower()
            name = attr_dict.get("name", "").lower()
            if prop in {"og:description", "twitter:description"} or name in {"description", "twitter:description"}:
                content = attr_dict.get("content", "").strip()
                if content:
                    self.description = content
        elif tag_lower == "p":
            self._in_p = True
            self._current_p = []

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()

        if self._skip_tags_stack and tag_lower == self._skip_tags_stack[-1]:
            self._skip_tags_stack.pop()
            self._skip_tag = bool(self._skip_tags_stack)
            return

        if self._skip_tag:
            return

        if tag_lower == "title":
            self._in_title = False
        elif tag_lower == "p":
            self._in_p = False
            p_text = "".join(self._current_p).strip()
            if len(p_text) > 20:
                self.paragraphs.append(p_text)
            self._current_p = []

    def handle_data(self, data: str):
        if self._skip_tag:
            return

        clean_data = re.sub(r"\s+", " ", data)
        if self._in_title:
            self.title += clean_data
        elif self._in_p:
            self._current_p.append(clean_data)


class URLScraper:
    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 (SiberSosialVerifier/1.0)"
        )

    def validate_url(self, url: str) -> str:
        if not url or not isinstance(url, str):
            raise ValueError("URL rujukan tidak boleh kosong.")

        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"Protokol URL '{parsed.scheme}' tidak didukung. Gunakan HTTP atau HTTPS.")

        if parsed.username or parsed.password:
            raise ValueError("URL tidak boleh mengandung kredensial tersemat.")

        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Format URL tidak valid (nama host tidak ditemukan).")

        if hostname.lower() in BLOCKED_HOSTNAMES or hostname.lower().endswith((".local", ".internal", ".localhost")):
            raise ValueError(f"Akses ke host internal '{hostname}' diblokir.")

        try:
            addr_info = socket.getaddrinfo(hostname, None)
        except socket.gaierror as exc:
            raise ValueError(f"Gagal melakukan resolusi DNS untuk '{hostname}': {exc}") from exc

        for entry in addr_info:
            ip_str = entry[4][0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                continue

            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_unspecified
                or ip.is_multicast
            ):
                raise ValueError(f"Akses ke alamat IP privat/internal '{ip_str}' diblokir (proteksi SSRF).")

        return parsed.geturl()

    def scrape(self, url: str) -> dict:
        target_url = self.validate_url(url)
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id,en;q=0.9",
        }

        current_url = target_url
        max_redirects = 3

        with requests.Session() as session:
            for _ in range(max_redirects):
                with session.get(
                    current_url,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=False,
                    stream=True,
                ) as resp:
                    if resp.is_redirect or resp.is_permanent_redirect:
                        next_url = resp.headers.get("Location")
                        if not next_url:
                            break
                        current_url = self.validate_url(urljoin(current_url, next_url))
                        continue

                    resp.raise_for_status()

                    content_type = resp.headers.get("Content-Type", "").lower()
                    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                        raise ValueError(f"Tipe konten bukan HTML ({content_type}).")

                    content_len = resp.headers.get("Content-Length")
                    if content_len and content_len.isdigit() and int(content_len) > MAX_SCRAPE_BYTES:
                        raise ValueError("Ukuran halaman melebihi batas maksimal 2 MB.")

                    chunks: list[bytes] = []
                    total_bytes = 0
                    for chunk in resp.iter_content(chunk_size=65536):
                        if not chunk:
                            continue
                        total_bytes += len(chunk)
                        if total_bytes > MAX_SCRAPE_BYTES:
                            raise ValueError("Ukuran halaman melebihi batas maksimal 2 MB.")
                        chunks.append(chunk)

                    encoding = resp.encoding or "utf-8"
                    html_text = b"".join(chunks).decode(encoding, errors="replace")

                parser = ArticleHTMLParser()
                parser.feed(html_text)

                title = parser.title.strip()
                description = parser.description.strip()
                body_text = " ".join(parser.paragraphs).strip()

                combined_parts = []
                if title:
                    combined_parts.append(title)
                if description and description not in body_text:
                    combined_parts.append(description)
                if body_text:
                    combined_parts.append(body_text)

                full_text = "\n\n".join(combined_parts)
                words = full_text.split()

                return {
                    "source_url": current_url,
                    "title": title or "Tanpa Judul",
                    "description": description,
                    "text": full_text,
                    "word_count": len(words),
                }

        raise ValueError("Melebihi batas pengalihan URL (too many redirects).")
