"""Public startup directories and employer pages; no account or outbound actions."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup, Tag

from hcis.sources.ats.adapters import (
    AshbyAdapter,
    GreenhouseAdapter,
    LeverAdapter,
    PublicFeedAdapter,
)

Row = dict[str, Any]
USER_AGENT = "HCIS-CareerResearch/1.0 (personal read-only research)"
SOCIAL_HOSTS = {
    "linkedin.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "crunchbase.com",
    "youtube.com",
    "instagram.com",
    "weixin.qq.com",
}


def public_url(value: str, base: str = "") -> str:
    raw = urljoin(base, value.strip())
    if any(ord(char) < 32 for char in raw) or "\\" in raw:
        raise ValueError("Invalid public URL")
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"https", "http"} or not host or parts.username or parts.password:
        raise ValueError("Only public HTTP URLs without credentials are accepted")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Local network URLs are not research sources")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError("Private network URLs are not research sources")
    if parts.port not in {None, 80, 443}:
        raise ValueError("Nonstandard network ports are not research sources")
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))


def domain(value: str) -> str:
    return (urlsplit(value).hostname or "").lower().removeprefix("www.")


def job_url(value: str) -> str:
    parts = urlsplit(public_url(value))
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc.lower(),
            parts.path.rstrip("/").removesuffix("/application"),
            parts.query,
            "",
        )
    )


def visible_text(node: Tag | BeautifulSoup) -> str:
    # Webflow leaves an exit label in every record, including currently active companies.
    copy = BeautifulSoup(str(node), "html.parser")
    for hidden in copy.select(
        "script, style, nav, footer, [hidden], [aria-hidden='true'], .w-condition-invisible"
    ):
        hidden.decompose()
    return copy.get_text(" ", strip=True)


class PublicWeb:
    """One bounded HTTP client shared by a research run; robots failures stay visible."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=18, headers={"User-Agent": USER_AGENT})
        self.robots: dict[str, RobotFileParser | None] = {}

    def close(self) -> None:
        self.client.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        current = public_url(url)
        for _ in range(5):
            response = self.client.request(method, current, follow_redirects=False, **kwargs)
            if response.is_redirect:
                current = public_url(response.headers["location"], current)
                continue
            response.raise_for_status()
            if len(response.content) > 32_000_000:
                raise ValueError("Research response exceeds 32 MB")
            return response
        raise ValueError("Too many source redirects")

    def get(self, url: str) -> httpx.Response:
        target = public_url(url)
        parts = urlsplit(target)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self.robots:
            try:
                response = self._request("GET", origin + "/robots.txt")
            except httpx.HTTPStatusError as error:
                if error.response.status_code not in {404, 410}:
                    raise
                self.robots[origin] = None
            else:
                parser = RobotFileParser()
                parser.parse(response.text.splitlines())
                self.robots[origin] = parser
        policy = self.robots[origin]
        if policy and (
            not policy.can_fetch(USER_AGENT, target) or not policy.can_fetch("ChatGPT-User", target)
        ):
            raise PermissionError(f"robots restrict automated research: {origin}")
        return self._request("GET", target)

    def get_feed(self, url: str) -> httpx.Response:
        # These are the published posting APIs already used by the project's ATS adapters.
        # Their /robots.txt can require authentication although their posting feed is public.
        target = public_url(url)
        host, path = domain(target), urlsplit(target).path
        allowed = {
            "api.ashbyhq.com": "/posting-api/job-board/",
            "boards-api.greenhouse.io": "/v1/boards/",
            "api.lever.co": "/v0/postings/",
        }
        if host not in allowed or not path.startswith(allowed[host]):
            raise ValueError("Not a supported public posting API")
        return self._request("GET", target)


def _external_links(soup: BeautifulSoup | Tag, origin: str) -> list[str]:
    found = []
    for anchor in soup.select("a[href]"):
        try:
            url = public_url(str(anchor.get("href", "")), origin)
        except ValueError:
            continue
        host = domain(url)
        if host != domain(origin) and not any(
            host == s or host.endswith("." + s) for s in SOCIAL_HOSTS
        ):
            found.append(url)
    return list(dict.fromkeys(found))


def parse_crv(html: str, url: str) -> list[Row]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for heading in soup.select("h3[id^='company-accordion-heading-']"):
        slug = str(heading["id"]).removeprefix("company-accordion-heading-")
        card = soup.find(id=slug)
        if not isinstance(card, Tag):
            continue
        links = _external_links(card, url)
        about = card.find("h4", string="About")
        detail = about.find_next_sibling() if about else None
        text = visible_text(card)
        rows.append(
            {
                "name": heading.get_text(strip=True),
                "detail_url": url + "#" + slug,
                "website": links[0] if links else None,
                "description": visible_text(detail) if isinstance(detail, Tag) else "",
                "category": "Featured" if "Featured" in text else "All",
                "stage": "IPO"
                if re.search(r"\bIPO\b", text)
                else ("Acquired" if "Acquired by" in text else None),
                "directory_evidence": text,
            }
        )
    return rows


def parse_sourcecode(html: str, url: str) -> list[Row]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for card in soup.select(".company-info-hide"):
        name = card.select_one(".company-info-name")
        desc = card.select_one(".company-info-desc")
        if name is None:
            continue
        links = _external_links(card, url)
        section = card.find_previous("h3")
        rows.append(
            {
                "name": name.get_text(strip=True),
                "website": links[0] if links else None,
                "detail_url": url,
                "description": desc.get_text(" ", strip=True) if desc else "",
                "category": section.get_text(" ", strip=True) if section else None,
                "stage": None,
            }
        )
    return rows


def parse_mindworks(html: str, url: str) -> list[Row]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, Row] = {}
    for anchor in soup.select("a[href^='/logos/']"):
        detail_url = public_url(str(anchor["href"]), url)
        slug = urlsplit(detail_url).path.rsplit("/", 1)[-1]
        exited = "已退出" in visible_text(anchor) or "Exited" in visible_text(anchor)
        pane = anchor.find_parent(attrs={"data-w-tab": True})
        category = {"Tab 4": "人工智能", "Tab 5": "金融科技", "Tab 6": "物流"}.get(
            str(pane.get("data-w-tab")) if pane else "", "全部"
        )
        if detail_url not in found:
            found[detail_url] = {
                "name": slug.replace("-", " "),
                "detail_url": detail_url,
                "website": None,
                "description": "",
                "name_verified": False,
                "category": category,
                "stage": "Exited" if exited else None,
            }
        if category != "全部":
            found[detail_url]["category"] = category
    return list(found.values())


def parse_sequoia_index(payload: Any, url: str) -> list[Row]:
    if not isinstance(payload, dict):
        raise ValueError("Sequoia public search index is not an object")
    rows = []
    for path, item in payload.items():
        if not path.startswith("/companies/") or not isinstance(item, dict):
            continue
        paragraphs = item.get("p", [])
        # The domain is published as its own paragraph in the site's search index.
        sites = [
            line
            for line in paragraphs
            if isinstance(line, str)
            and re.fullmatch(r"(?:https?://)?(?:www\.)?[\w-]+(?:\.[\w-]+)+/?", line)
            and not line.endswith("sequoiacap.com")
        ]
        website = (
            public_url(sites[0] if sites[0].startswith("http") else "https://" + sites[0])
            if sites
            else None
        )
        rows.append(
            {
                "name": str(item.get("title", "")).split(" | ")[0],
                "description": item.get("description", ""),
                "detail_url": urljoin(url, path),
                "website": website,
                "directory_evidence": " · ".join(
                    str(line)
                    for line in paragraphs
                    if re.match(r"Founded|Partnered|IPO|Acquired", str(line))
                ),
                "stage": None,
                "category": "公开公司详情索引",
            }
        )
    return rows


def fetch_directory(web: PublicWeb, spec: Row) -> Row:
    url = spec["url"]
    response = web.get(url)
    html = response.text
    parser = spec["parser"]
    evidence_urls = [str(response.url)]
    scope = "公开名录全部已返回的公司卡片"
    if parser == "sequoia":
        soup = BeautifulSoup(html, "html.parser")
        index = soup.find("meta", attrs={"name": "framer-search-index"})
        if not isinstance(index, Tag) or not index.get("content"):
            raise ValueError(
                "Sequoia public search index link is missing; browser capture required"
            )
        index_url = public_url(str(index["content"]), url)
        if not re.fullmatch(
            r"https://framerusercontent\.com/sites/[\w-]+/searchIndex-[\w-]+\.json", index_url
        ):
            raise ValueError("Unexpected public search index resource URL")
        # The allowed website explicitly declares this JSON asset, like its page scripts.
        # CDN /robots.txt is not a posting API or a site directory to crawl.
        data = web._request("GET", index_url).json()
        rows = parse_sequoia_index(data, url)
        evidence_urls.append(index_url)
        scope = "官网公开搜索索引中的公司详情；与 All Companies 视图对照另行记录"
    else:
        rows = {"crv": parse_crv, "mindworks": parse_mindworks, "sourcecode": parse_sourcecode}[
            parser
        ](html, url)
    if not rows:
        raise ValueError("Directory returned no recognizable company cards; not treated as zero")
    return {
        "schema_version": 1,
        "source": spec["id"],
        "captured_at": datetime.now(UTC).isoformat(),
        "companies": rows,
        "coverage": {
            "complete": True,
            "scope": scope,
            "returned": len(rows),
            "evidence_urls": evidence_urls,
        },
    }


def _ats_board(url: str) -> tuple[str, str] | None:
    parts = urlsplit(url)
    path = parts.path.strip("/").split("/")
    host = domain(url)
    if host == "jobs.ashbyhq.com" and path[0]:
        return "ashby", path[0]
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and path[0] not in {
        "",
        "embed",
    }:
        return "greenhouse", path[0]
    if host == "jobs.lever.co" and path[0]:
        return "lever", path[0]
    return None


def read_board(web: PublicWeb, provider: str, board_id: str) -> tuple[list[Row], Row]:
    adapters: dict[str, Callable[[str], PublicFeedAdapter]] = {
        "ashby": AshbyAdapter,
        "greenhouse": GreenhouseAdapter,
        "lever": LeverAdapter,
    }
    adapter = adapters[provider](board_id)
    payload = web.get_feed(adapter.feed_url).json()
    raw = payload if provider == "lever" else payload.get("jobs")
    if not isinstance(raw, list):
        raise ValueError("Official board has no valid job list")
    if provider == "ashby":
        payload = {**payload, "jobs": [job for job in raw if job.get("isListed", True)]}
    posts = adapter.parse_payload(payload)
    jobs = [
        {
            "title": post.title,
            "location": post.location,
            "description": post.description,
            "url": post.canonical_url,
            "posted_at": post.posted_at.isoformat() if post.posted_at else None,
            "provider": provider,
            "board": f"{provider}:{board_id}",
            "employment_type": post.employment_type,
        }
        for post in posts
    ]
    return jobs, {
        "id": f"{provider}:{board_id}",
        "complete": True,
        "count": len(posts),
        "url": adapter.feed_url,
    }


def identify_jobs(result: Row) -> None:
    current = result["company"]
    for job in result["jobs"]:
        job["url"] = job_url(job["url"])
        job["id"] = "discovery-job-" + hashlib.sha256(job["url"].encode()).hexdigest()[:24]
        job["company"] = current["name"]
        job["website"] = current["website"]
        job["source"] = current["source"]
        job["entry_id"] = current["id"]
        job["observed_at"] = result["observed_at"]


def read_employer(web: PublicWeb, company: Row) -> Row:
    """Follow only published employer links; a failed board never closes stored jobs."""
    result: Row = {
        "company": dict(company),
        "jobs": [],
        "pages": [],
        "errors": [],
        "boards": [],
        "observed_at": datetime.now(UTC).isoformat(),
    }
    current = result["company"]
    if current["source"] == "mindworks":
        response = web.get(current["detail_url"])
        soup = BeautifulSoup(response.text, "html.parser")
        if soup.title:
            current["name"] = soup.title.get_text().split(" | ")[0]
            current["name_verified"] = True
        sites = _external_links(soup, current["detail_url"])
        current["website"] = next(
            (
                s
                for s in sites
                if not any(
                    word in domain(s) for word in ("geekwire", "rive.app", "weglot", "mindworks")
                )
            ),
            None,
        )
        current["detail_text"] = visible_text(soup)[:16000]
        result["pages"].append({"url": str(response.url), "text": current["detail_text"]})
    if not current.get("website"):
        result["errors"].append("未在渠道公开资料中确认公司官网；不猜测域名")
        return result
    website = public_url(current["website"])
    site = urlsplit(website)
    home = f"{site.scheme}://{site.netloc}/"
    response = web.get(home)
    soup = BeautifulSoup(response.text, "html.parser")
    home_text = visible_text(soup)
    current["official_description"] = home_text[:18000]
    result["pages"].append({"url": str(response.url), "text": home_text[:18000]})
    career_links: list[str] = []
    board_links: list[str] = []
    for anchor in soup.select("a[href]"):
        try:
            link = public_url(str(anchor["href"]), str(response.url))
        except ValueError:
            continue
        if _ats_board(link):
            board_links.append(link)
        elif domain(link) == domain(home) and re.search(
            r"careers?|\bjobs\b|join.us|招聘|加入我们",
            anchor.get_text(" ", strip=True) + " " + urlsplit(link).path,
            re.I,
        ):
            career_links.append(link)
    for link in list(dict.fromkeys(career_links))[:2]:
        try:
            response = web.get(link)
            career = BeautifulSoup(response.text, "html.parser")
            result["pages"].append({"url": str(response.url), "text": visible_text(career)[:18000]})
            links = [
                public_url(str(a["href"]), str(response.url))
                for a in career.select("a[href]")
                if str(a["href"]).startswith(("/", "http"))
            ]
            board_links.extend(item for item in links if _ats_board(item))
            # Some employer sites render the board in a script or iframe instead of an anchor.
            board_links.extend(
                re.findall(
                    r"https://(?:jobs\.ashbyhq\.com|job-boards\.greenhouse\.io|boards\.greenhouse\.io|jobs\.lever\.co)/[\w-]+",
                    response.text,
                )
            )
            if not any(_ats_board(item) for item in links):
                role_links = [
                    item
                    for item in links
                    if domain(item) == domain(home)
                    and re.search(r"/(?:careers|jobs)/[^/?#]+", urlsplit(item).path)
                ]
                for role_url in list(dict.fromkeys(role_links))[:8]:
                    role_response = web.get(role_url)
                    role_soup = BeautifulSoup(role_response.text, "html.parser")
                    heading = role_soup.find("h1")
                    body = visible_text(role_soup)
                    if heading and re.search(r"full.time|全职|employment|职位|岗位", body, re.I):
                        result["jobs"].append(
                            {
                                "title": heading.get_text(" ", strip=True),
                                "location": None,
                                "description": body,
                                "url": role_url,
                                "posted_at": None,
                                "provider": "employer_page",
                                "employment_type": None,
                            }
                        )
                if len(set(role_links)) > 8:
                    result["errors"].append("官网职位详情超过本轮 8 页读取上限；覆盖为部分")
        except (httpx.HTTPError, ValueError, PermissionError) as error:
            result["errors"].append(f"{domain(link)}: {type(error).__name__}: {error}")
    seen: set[tuple[str, str]] = set()
    for link in board_links:
        board = _ats_board(link)
        if board is None or board in seen:
            continue
        seen.add(board)
        provider, board_id = board
        try:
            jobs, coverage = read_board(web, provider, board_id)
            result["jobs"].extend(jobs)
            result["boards"].append(coverage)
        except (httpx.HTTPError, ValueError, PermissionError, KeyError, TypeError) as error:
            result["errors"].append(f"{provider}:{board_id}: {type(error).__name__}: {error}")
            result["boards"].append({"id": f"{provider}:{board_id}", "complete": False})
    if not result["jobs"] and not result["boards"]:
        result["errors"].append("未发现可解析的官方岗位；需要继续人工核查，不代表没有招聘")
    identify_jobs(result)
    return result


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()
