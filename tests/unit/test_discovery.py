from __future__ import annotations

import httpx
import pytest

from hcis.sources.discovery import (
    PublicWeb,
    parse_crv,
    parse_mindworks,
    parse_sequoia_index,
    parse_sourcecode,
    public_url,
)


def test_directories_preserve_company_details_and_ignore_hidden_exit_labels() -> None:
    crv = parse_crv(
        """<div id="builder"><h3 id="company-accordion-heading-builder">Builder</h3>
        <span>Featured</span><h4>About</h4><p>Agent review tools</p>
        <a href="https://builder.example/">Website</a><p>2024 - Partnered</p></div>""",
        "https://www.crv.com/companies",
    )
    assert crv[0]["name"] == "Builder" and crv[0]["category"] == "Featured"
    assert crv[0]["description"] == "Agent review tools"
    sourcecode = parse_sourcecode(
        """<h3>AI &amp; Robotics</h3>
        <div class="company-info-hide"><div class="company-info-name">创造工具</div>
        <a href="https://creator.example/"><img></a>
        <div class="company-info-desc">生成式创作</div></div>""",
        "https://sourcecodecap.com/companies/",
    )
    assert sourcecode[0]["website"] == "https://creator.example/"
    assert sourcecode[0]["category"] == "AI & Robotics"
    mindworks = parse_mindworks(
        """<div data-w-tab="Tab 1">
        <a href="/logos/active"><div class="w-condition-invisible">已退出</div></a>
        <a href="/logos/exited"><div>已退出</div></a></div>
        <div data-w-tab="Tab 4"><a href="/logos/active"><div hidden>已退出</div></a></div>""",
        "https://sc.mindworks.vc/portfolio",
    )
    assert len(mindworks) == 2
    assert mindworks[0]["stage"] is None and mindworks[0]["category"] == "人工智能"
    assert mindworks[1]["stage"] == "Exited"


def test_sequoia_uses_the_published_company_index_without_guessing_a_domain() -> None:
    rows = parse_sequoia_index(
        {
            "/companies/builder": {
                "title": "Builder | Sequoia Capital",
                "description": "Agent tools",
                "p": ["builder.example", "Founded 2024", "Partnered 2025"],
            },
            "/companies/unknown": {
                "title": "Unknown | Sequoia Capital",
                "p": ["No website disclosed"],
            },
            "/people/person": {"title": "Person"},
        },
        "https://sequoiacap.com/our-companies?spotlight=no",
    )
    assert len(rows) == 2 and rows[0]["website"] == "https://builder.example/"
    assert rows[1]["website"] is None and rows[0]["stage"] is None


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "http://localhost/",
        "file:///tmp/test",
        "https://user:secret@example.com/",
        "https://example.com:8000/",
        "https://example.com\n/private",
    ],
)
def test_source_urls_cannot_target_local_services_or_carry_credentials(url: str) -> None:
    with pytest.raises(ValueError):
        public_url(url)


def test_robots_denial_is_not_bypassed_by_the_research_clients_user_agent() -> None:
    visited: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        visited.append(str(request.url))
        return httpx.Response(200, text="User-agent: ChatGPT-User\nDisallow: /\n")

    web = PublicWeb(httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(PermissionError):
        web.get("https://publisher.example/startups/")
    assert visited == ["https://publisher.example/robots.txt"]
    web.close()


def test_published_posting_feed_is_read_directly_but_endpoint_auth_failure_is_preserved() -> None:
    visited: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        visited.append(str(request.url))
        return httpx.Response(
            401 if request.url.path.endswith("private") else 200, json={"jobs": []}
        )

    web = PublicWeb(httpx.Client(transport=httpx.MockTransport(handler)))
    assert web.get_feed("https://api.ashbyhq.com/posting-api/job-board/public").json() == {
        "jobs": []
    }
    with pytest.raises(httpx.HTTPStatusError):
        web.get_feed("https://api.ashbyhq.com/posting-api/job-board/private")
    with pytest.raises(ValueError):
        web.get_feed("https://api.ashbyhq.com/unpublished/path")
    assert len(visited) == 2 and not any("robots.txt" in url for url in visited)
    web.close()
