#!/usr/bin/env python3
"""CDP-based trend providers for 小红书 / 知乎 / 微信公众号 / 豆瓣 / 虎扑.

These platforms are JS-rendered and anti-scraped, so static HTTP (tavily/exa/etc.)
can't read their real content or engagement. Instead we drive the user's real,
logged-in browser through the web-access CDP proxy (see cdp_client.py): navigate
to the platform's search page, then run a small JS extractor in the page to pull
structured results (title + url + real engagement) into our common schema.

通过 web-access 的 CDP Proxy 驱动用户**真实已登录**浏览器，访问各平台搜索页并在页面里
跑 JS 提取真实结果与互动量，归一化为统一 schema。覆盖：小红书、知乎、微信公众号、豆瓣、虎扑。

Each platform = (search_url builder, JS extractor). Adding a platform is just one
more entry in PLATFORM_SPECS — no new transport code.
"""

import argparse
import json
import sys
from urllib.parse import quote

try:
    from . import _common
    from .cdp_client import CDPClient, CDPError, ConsentRequired
except ImportError:  # standalone script
    import _common
    from cdp_client import CDPClient, CDPError, ConsentRequired


# ---------------------------------------------------------------------------
# JS extractors. Each runs in the platform's search-result page and returns an
# array of {title, url, snippet, likes, comments, saves, shares, published}.
# Selectors are best-effort and defensive: these DOMs change, so every field is
# guarded and missing values come back null rather than throwing. Keep the JS
# resilient — partial data still ranks usefully by whatever engagement exists.
# ---------------------------------------------------------------------------

# 小红书: search-result note cards. Likes are the visible 互动 count on each card.
# Returns {login_required, items[]} — XHS gates search behind login, so we detect
# the login wall in-page and signal it rather than returning a silent empty list.
# Each note renders two anchors (a hidden /explore/ link + the visible card with a
# /search_result/?xsec_token link); we key by note id and keep the card that has a
# title, so every note appears once with its real clickable URL.
_XHS_JS = r"""
(() => {
  const num = (t) => {
    if (!t) return null;
    const m = String(t).match(/([\d.]+)\s*(万|w|k)?/i);
    if (!m) return null;
    let v = parseFloat(m[1]);
    const u = (m[2] || '').toLowerCase();
    if (u === '万' || u === 'w') v *= 1e4;
    else if (u === 'k') v *= 1e3;
    return Math.round(v);
  };
  const noteId = (href) => {
    const m = String(href || '').match(/\/(?:explore|search_result)\/([0-9a-f]+)/);
    return m ? m[1] : null;
  };
  const bodyText = (document.body?.innerText || '');
  const byId = new Map();
  document.querySelectorAll('section.note-item, div.note-item').forEach((card) => {
    const titleEl = card.querySelector('.title, a.title, span.title, .note-text');
    const title = (titleEl?.innerText || titleEl?.textContent || '').trim();
    const likeEl = card.querySelector('.like-wrapper .count, .count, span.like');
    const account = (
      card.querySelector('.footer .author .name, .author-wrapper .name, .author .name, .user .name, .user-name, .nickname')?.innerText
      || card.querySelector('a[href*="/user/profile/"] span, a[href*="/user/profile/"]')?.innerText
      || ''
    ).trim();
    // Prefer the canonical /search_result link (carries xsec_token), else /explore.
    const linkEl = card.querySelector('a[href*="/search_result/"]')
                || card.querySelector('a[href*="/explore/"]')
                || card.querySelector('a.cover');
    let href = linkEl?.getAttribute('href') || '';
    if (href && href.startsWith('/')) href = 'https://www.xiaohongshu.com' + href;
    const id = noteId(href);
    if (!id || !title) return;          // skip the hidden, title-less duplicate anchor
    const prev = byId.get(id);
    if (prev && prev.title) return;     // already have a good row for this note
    byId.set(id, {
      title, url: href, snippet: '',
      likes: num(likeEl?.innerText), comments: null, saves: null, shares: null,
      account, author: account,
      published: '',
    });
  });
  const items = Array.from(byId.values());
  const login_required = items.length === 0 && /登录后查看|扫码登录|手机号登录/.test(bodyText);
  return { login_required, items: items.slice(0, 40) };
})()
"""

# 知乎: search-result list. 赞同/评论 live in the action buttons' text
# ("赞同 55", "60 条评论"). Returns {login_required, items[]}; results need login.
_ZHIHU_JS = r"""
(() => {
  const num = (t) => {
    if (!t) return null;
    const m = String(t).replace(/,/g, '').match(/([\d.]+)\s*(万|w|k)?/i);
    if (!m) return null;
    let v = parseFloat(m[1]);
    const u = (m[2] || '').toLowerCase();
    if (u === '万' || u === 'w') v *= 1e4; else if (u === 'k') v *= 1e3;
    return Math.round(v);
  };
  const bodyText = (document.body?.innerText || '');
  const items = [];
  const seen = new Set();
  document.querySelectorAll('.SearchResult-Card, .List-item').forEach((card) => {
    const titleEl = card.querySelector('h2 a, .ContentItem-title a, h2');
    const link = card.querySelector('h2 a, .ContentItem-title a, a[href*="/question/"], a[href*="/answer/"], a[href*="/p/"]');
    const title = (titleEl?.innerText || titleEl?.textContent || '').trim();
    let href = link?.getAttribute('href') || '';
    if (href && href.startsWith('//')) href = 'https:' + href;
    else if (href && href.startsWith('/')) href = 'https://www.zhihu.com' + href;
    if (!title || !href || seen.has(href)) return;
    seen.add(href);

    // Engagement + date live in the action row text, e.g.
    //   "赞同 55 ​ 60 条评论 2024-01-20"
    // Use targeted regexes so 赞同 and 评论 don't read each other's number.
    const cardText = (card.innerText || '').replace(/​/g, ' ');
    let author = (
      card.querySelector('.AuthorInfo-name, .UserLink-link, .ContentItem-meta a[href*="/people/"], .ContentItem-meta a[href*="/org/"]')?.innerText
      || ''
    ).trim();
    if (!author && title) {
      const afterTitle = cardText.slice(cardText.indexOf(title) + title.length).trim();
      const m = afterTitle.match(/^([^\n：:]{2,32})[:：]/);
      if (m) author = m[1].trim();
    }
    const parseNear = (re) => { const m = cardText.match(re); return m ? num(m[1]) : null; };
    const likes = parseNear(/赞同\s*([\d.]+\s*[万wk]?)/i);
    const comments = parseNear(/([\d.]+\s*[万wk]?)\s*条?\s*评论/);
    const dateMatch = cardText.match(/(\d{4}-\d{2}-\d{2})/);

    items.push({
      title, url: href,
      snippet: (card.querySelector('.RichText, .SearchItem-excerpt, .CopyrightRichText-richText')?.innerText || '').trim().slice(0, 200),
      likes, comments, saves: null, shares: null,
      account: author, author,
      published: dateMatch ? dateMatch[1] : '',
    });
  });
  const login_required = items.length === 0 && /登录\/注册|扫码登录|安全验证/.test(bodyText);
  return { login_required, items: items.slice(0, 40) };
})()
"""

# 微信公众号 via Sogou weixin search (公开可搜的入口). Engagement isn't exposed on
# the search listing, so we return titles+links+source+date; ranking falls back to
# recency/relevance. Opening an article could read 阅读/在看, but that's a deeper crawl.
_WEIXIN_JS = r"""
(() => {
  const bodyText = (document.body?.innerText || '');
  const items = [];
  document.querySelectorAll('.news-box li, .news-list li, li[id^="sogou_vr"]').forEach((li) => {
    // The title anchor is inside <h3>; a bare `a` would grab the thumbnail link
    // (no text), so query h3 a explicitly with ordered fallbacks.
    const a = li.querySelector('h3 a') || li.querySelector('.txt-box h3 a')
              || li.querySelector('h3') || li.querySelector('a[href]');
    const title = (a?.innerText || a?.textContent || '').trim();
    const linkEl = li.querySelector('h3 a, .txt-box h3 a, a[href]');
    let href = linkEl?.getAttribute('href') || '';
    if (href && href.startsWith('/')) href = 'https://weixin.sogou.com' + href;
    const account = (li.querySelector('.account, .all-time-y2, .s-p a')?.innerText || '').trim();
    const snippet = (li.querySelector('.txt-info, p')?.innerText || '').trim().slice(0, 200);
    if (!title) return;
    items.push({ title, url: href, snippet, account, likes: null, comments: null, saves: null, shares: null, published: '' });
  });
  // Sogou shows an anti-bot verification page under heavy use.
  const login_required = items.length === 0 && /请输入验证码|访问验证|antispider/i.test(bodyText);
  return { login_required, items: items.slice(0, 40) };
})()
"""

# 豆瓣: global search result cards. The results page is React-rendered with
# `DouWeb-SR-*` class names (book/movie/music/tv "subject cards") that expose a
# rating and "N人评价"; rating → score, rating count → comments (nearest volume
# signal). Legacy `.result` selectors are kept as a fallback for group/topic
# results. We scope to those containers and reject bare domain-root hrefs so the
# global nav bar (读书/电影/音乐…) never leaks in as fake results.
_DOUBAN_JS = r"""
(() => {
  const num = (t) => {
    if (!t) return null;
    const m = String(t).replace(/,/g, '').match(/([\d.]+)\s*(万|w|k)?/i);
    if (!m) return null;
    let v = parseFloat(m[1]);
    const u = (m[2] || '').toLowerCase();
    if (u === '万' || u === 'w') v *= 1e4; else if (u === 'k') v *= 1e3;
    return Math.round(v);
  };
  const isRealResult = (href) => {
    // Reject nav: bare domain roots like https://book.douban.com or /group .
    if (!href) return false;
    try {
      const u = new URL(href, location.origin);
      if (u.pathname === '' || u.pathname === '/') return false;
      return true;
    } catch { return false; }
  };
  const bodyText = (document.body?.innerText || '');
  const items = [];
  const seen = new Set();
  document.querySelectorAll(
    '.DouWeb-SR-subject-card, .result, .result-list .item, .search-result .item'
  ).forEach((card) => {
    const link = card.querySelector(
      '.DouWeb-SR-subject-info-name, .title a, h3 a, h2 a, a[href*="douban.com"]'
    );
    const title = (link?.innerText || link?.textContent || '').trim();
    let href = link?.getAttribute('href') || '';
    if (href && href.startsWith('//')) href = 'https:' + href;
    if (!title || !isRealResult(href) || seen.has(href)) return;
    seen.add(href);
    const text = (card.innerText || '').replace(/\s+/g, ' ').trim();
    const ratingMatch = text.match(/(?:评分|豆瓣评分)?\s*([0-9]\.[0-9])(?!\d)/);
    const commentsMatch = text.match(/([\d,.]+\s*[万wk]?)\s*人?(?:评价|评分|看过|讨论)/i);
    const yearMatch = text.match(/(20\d{2}|19\d{2})/);
    const typeEl = card.querySelector('.DouWeb-SR-subject-info-type-name');
    const typeTag = (typeEl?.innerText || '').trim();
    const author = (
      card.querySelector('.DouWeb-SR-subject-info-subtitle a, .info a[href*="/people/"], .content .meta a, .subject-cast a')?.innerText
      || ''
    ).trim();
    items.push({
      title: typeTag ? `${typeTag} ${title}` : title,
      url: href,
      snippet: text.slice(0, 220),
      score: ratingMatch ? parseFloat(ratingMatch[1]) : null,
      likes: null,
      comments: commentsMatch ? num(commentsMatch[1]) : null,
      saves: null, shares: null, views: null,
      account: author, author,
      published: yearMatch ? yearMatch[1] + '-01-01' : '',
    });
  });
  if (items.length === 0) {
    const lines = bodyText.split(/\n+/).map(s => s.trim()).filter(Boolean);
    const start = lines.findIndex(s => /相关内容/.test(s));
    const end = lines.findIndex((s, i) => i > start && /显示更多|对结果不满意/.test(s));
    const slice = lines.slice(start >= 0 ? start + 1 : 0, end > 0 ? end : lines.length);
    for (let i = 0; i < slice.length - 1 && items.length < 40; i++) {
      const line = slice[i];
      const next = slice[i + 1] || '';
      let title = line, account = '';
      let likes = null, comments = null;
      let m = next.match(/([\d.]+\s*[万wk]?)赞\s*[· ]\s*([\d.]+\s*[万wk]?)回复/i);
      if (m) {
        likes = num(m[1]); comments = num(m[2]);
        account = slice[i + 2] || '';
      } else {
        m = line.match(/^(.{2,32}?)\s+([\d.]+\s*[万wk]?)赞\s*[· ]\s*([\d.]+\s*[万wk]?)回复/i);
        if (!m) continue;
        account = m[1].trim(); likes = num(m[2]); comments = num(m[3]);
        title = slice[i - 1] || line;
      }
      if (!title || /小组$|登录|注册|全部/.test(title)) continue;
      items.push({
        title, url: '', snippet: slice.slice(i, i + 4).join(' ').slice(0, 220),
        score: null, likes, comments, saves: null, shares: null, views: null,
        account, author: account, published: '',
      });
    }
  }
  const login_required = items.length === 0 && /登录|注册|安全验证/.test(bodyText);
  return { login_required, items: items.slice(0, 40) };
})()
"""

# 虎扑: forum search results. Each hit is a `.content-wrap` row: a thread-link
# anchor (bbs.hupu.com/<id>.html), a 专区 link, a date, then three numeric spans
# in column order 回复(replies) | 推荐(recommend) | 亮评数(highlights). We map
# 回复→comments, 推荐→likes, and keep 亮评数 as a secondary signal. Legacy broad
# selectors are kept as a fallback, but we require a thread-id href so the global
# nav bar (NBA版/社区首页…) can't leak in as fake results.
_HUPU_JS = r"""
(() => {
  const num = (t) => {
    if (!t) return null;
    const m = String(t).replace(/,/g, '').match(/([\d.]+)\s*(万|w|k)?/i);
    if (!m) return null;
    let v = parseFloat(m[1]);
    const u = (m[2] || '').toLowerCase();
    if (u === '万' || u === 'w') v *= 1e4; else if (u === 'k') v *= 1e3;
    return Math.round(v);
  };
  const isThread = (href) => /\/\d{6,}\.html/.test(String(href || ''));
  const bodyText = (document.body?.innerText || '');
  const items = [];
  const seen = new Set();
  document.querySelectorAll('.content-wrap, .search-list li, .post-list li, .result').forEach((card) => {
    // The first thread-link anchor is the title; other anchors are 专区/tag links.
    const link = [...card.querySelectorAll('a')].find((a) => isThread(a.getAttribute('href')));
    if (!link) return;
    const title = (link.innerText || link.textContent || '').trim();
    let href = link.getAttribute('href') || '';
    if (href && href.startsWith('//')) href = 'https:' + href;
    else if (href && href.startsWith('/')) href = 'https://bbs.hupu.com' + href;
    if (!title || title.length < 4 || seen.has(href)) return;
    seen.add(href);
    // New DOM exposes the three counts as ordered .content-wrap-span1 spans:
    //   回复(replies) | 推荐(recommend) | 亮评数(highlights)
    const counts = [...card.querySelectorAll('.content-wrap-span1')]
      .map((s) => num(s.innerText));
    let comments = counts[0] ?? null;   // 回复
    let likes = counts[1] ?? null;      // 推荐
    // Fallback to label-based parsing for the legacy DOM.
    const text = (card.innerText || '').replace(/\s+/g, ' ').trim();
    const parseNear = (re) => { const m = text.match(re); return m ? num(m[1]) : null; };
    if (comments === null) {
      comments = parseNear(/([\d,.]+\s*[万wk]?)\s*(?:回复|回帖|评论)/i)
              || parseNear(/(?:回复|回帖|评论)\s*([\d,.]+\s*[万wk]?)/i);
    }
    if (likes === null) {
      likes = parseNear(/([\d,.]+\s*[万wk]?)\s*(?:亮|点亮|推荐)/i)
           || parseNear(/(?:亮|点亮|推荐)\s*([\d,.]+\s*[万wk]?)/i);
    }
    const views = parseNear(/([\d,.]+\s*[万wk]?)\s*(?:浏览|阅读)/i)
               || parseNear(/(?:浏览|阅读)\s*([\d,.]+\s*[万wk]?)/i);
    const dateMatch = text.match(/(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2})/);
    const rawLines = (card.innerText || '').split(/\n+/).map(s => s.trim()).filter(Boolean);
    const titleLine = rawLines.findIndex(s => s === title);
    const board = titleLine >= 0 ? (rawLines[titleLine + 1] || '') : '';
    const author = (
      card.querySelector('.user-name, .username, .post-user, .author, a[href*="/profile/"], a[href*="/user/"]')?.innerText
      || board
      || ''
    ).trim();
    items.push({
      title, url: href,
      snippet: text.slice(0, 220),
      likes, comments, saves: null, shares: null, views,
      account: author, author,
      published: dateMatch ? dateMatch[1] : '',
    });
  });
  if (items.length === 0) {
    const lines = bodyText.split(/\n+/).map(s => s.trim()).filter(Boolean);
    const header = lines.findIndex(s => s === '帖子');
    const slice = lines.slice(header >= 0 ? header + 6 : 0);
    for (let i = 0; i < slice.length - 5 && items.length < 40; i += 6) {
      const title = slice[i];
      const board = slice[i + 1];
      const date = slice[i + 2];
      const comments = num(slice[i + 3]);
      const likes = num(slice[i + 4]);
      const highlights = num(slice[i + 5]);
      if (!title || !/\d{4}-\d{1,2}-\d{1,2}/.test(date || '')) { i -= 5; continue; }
      items.push({
        title, url: '', snippet: `${board} ${date} 回复${slice[i + 3]} 推荐${slice[i + 4]} 亮评${slice[i + 5]}`.slice(0, 220),
        likes, comments, saves: null, shares: null, views: highlights,
        account: board, author: board, published: date,
      });
    }
  }
  const login_required = items.length === 0 && /登录|注册|安全验证/.test(bodyText);
  return { login_required, items: items.slice(0, 40) };
})()
"""


# 微博: server-side requests to m.weibo.cn now hit Sina's "Visitor System"
# anti-bot wall (HTTP 432), even after the visitor-cookie handshake — so the
# key-free weibo.py provider can't reach search anymore. But inside the user's
# logged-in browser the same JSON API works fine and returns full structured
# engagement (点赞/评论/转发). So we drive it via CDP: load m.weibo.cn, then
# fetch the same-origin search API in-page (cookies attached automatically) and
# normalize mblogs. This is more robust than DOM scraping and keeps real metrics.
def _weibo_js(query: str) -> str:
    payload = json.dumps(query)  # safely embed the query as a JS string literal
    return r"""
(async () => {
  const q = %s;
  const containerid = '100103type=1&q=' + q;
  const out = { login_required: false, items: [] };
  let data;
  try {
    const url = '/api/container/getIndex?containerid=' + encodeURIComponent(containerid)
              + '&page_type=searchall&page=1';
    const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (r.status !== 200) { out.login_required = r.status === 432 || r.status === 403; return out; }
    data = await r.json();
  } catch (e) { return out; }
  if (!data || (data.ok !== 1 && data.ok !== '1' && data.ok !== true)) return out;

  const strip = (t) => String(t || '').replace(/<[^>]+>/g, ' ')
                        .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
  const seen = new Set();
  const walk = (cards) => {
    for (const card of (cards || [])) {
      if (!card || typeof card !== 'object') continue;
      const m = card.mblog;
      if (m && typeof m === 'object') {
        const id = m.id || m.mblogid || m.bid;
        if (id && !seen.has(id)) {
          seen.add(id);
          const text = m.text_raw || strip(m.text);
          if (text) {
            const bid = m.bid || m.mblogid || m.id;
            out.items.push({
              title: text.slice(0, 80),
              url: m.scheme || (bid ? 'https://m.weibo.cn/detail/' + bid : ''),
              snippet: text.slice(0, 240),
              likes: m.attitudes_count ?? null,
              comments: m.comments_count ?? null,
              saves: null,
              shares: m.reposts_count ?? null,
              views: m.reads_count ?? null,
              author: (m.user && m.user.screen_name) || '',
              published: m.created_at || '',
            });
          }
        }
      }
      if (card.card_group) walk(card.card_group);
    }
  };
  walk(data.data?.cards || []);
  return out;
})()
""" % payload


def _xhs_url(query: str) -> str:
    return f"https://www.xiaohongshu.com/search_result?keyword={quote(query)}"


def _weibo_url(query: str) -> str:
    # Land on m.weibo.cn so the in-page fetch is same-origin (cookies attached).
    return "https://m.weibo.cn/"


def _zhihu_url(query: str) -> str:
    return f"https://www.zhihu.com/search?type=content&q={quote(query)}"


def _weixin_url(query: str) -> str:
    # Sogou is the public, searchable gateway to 公众号 articles.
    return f"https://weixin.sogou.com/weixin?type=2&query={quote(query)}"


def _douban_url(query: str) -> str:
    return f"https://www.douban.com/search?q={quote(query)}"


def _hupu_url(query: str) -> str:
    return f"https://bbs.hupu.com/search?q={quote(query)}"


# platform -> (search_url(query), extractor_js, settle_scrolls)
# extractor_js may be a string, or a callable(query) -> string for extractors that
# must embed the query (e.g. 微博's in-page API fetch).
PLATFORM_SPECS = {
    "xiaohongshu": (_xhs_url, _XHS_JS, 3),
    "zhihu": (_zhihu_url, _ZHIHU_JS, 3),
    "weixin": (_weixin_url, _WEIXIN_JS, 1),
    "douban": (_douban_url, _DOUBAN_JS, 1),
    "hupu": (_hupu_url, _HUPU_JS, 2),
    "weibo": (_weibo_url, _weibo_js, 0),
}

# Aliases so callers can use familiar names.
PLATFORM_ALIASES = {
    "xhs": "xiaohongshu", "redbook": "xiaohongshu", "小红书": "xiaohongshu",
    "zhihu": "zhihu", "知乎": "zhihu",
    "weixin": "weixin", "wechat": "weixin", "mp": "weixin", "公众号": "weixin",
    "douban": "douban", "db": "douban", "豆瓣": "douban",
    "hupu": "hupu", "虎扑": "hupu",
    "weibo": "weibo", "微博": "weibo",
}


def resolve_platform(platform: str) -> str:
    return PLATFORM_ALIASES.get(platform, platform)


def search(query: str, api_key=None, limit: int = 10, platform: str = "",
           client: "CDPClient" = None, consent: bool = False) -> dict:
    """Search a CDP platform and return a normalized envelope with engagement.

    `api_key` is accepted for a uniform provider signature but unused (the auth is
    the user's own browser session). `client` is injectable for tests.

    `consent` MUST be True to touch the browser. CDP drives the user's real,
    logged-in session, so without explicit consent we raise ConsentRequired before
    any navigation — the caller (dispatcher/SKILL.md) is responsible for asking.
    """
    canonical = resolve_platform(platform)
    if canonical not in PLATFORM_SPECS:
        raise CDPError(f"no CDP extractor for platform '{platform}'")

    if not consent:
        raise ConsentRequired(
            f"Searching {canonical} drives your real, logged-in browser. "
            f"Ask the user for consent, then retry with consent=True."
        )

    url_builder, extractor_js, scrolls = PLATFORM_SPECS[canonical]
    # Some extractors (微博) need the query embedded; they're provided as a callable.
    extractor = extractor_js(query) if callable(extractor_js) else extractor_js

    owns_client = client is None
    client = client or CDPClient()
    try:
        client.ensure_proxy()
        target_id = client.new_tab(url_builder(query))
        if scrolls:
            client.scroll(target_id, scrolls)  # trigger lazy-loaded cards
        raw = client.eval(target_id, extractor)
    finally:
        if owns_client:
            client.__exit__(None, None, None)

    # Extractors return {login_required, items[]}; tolerate a bare list too.
    if isinstance(raw, dict):
        login_required = bool(raw.get("login_required"))
        rows = raw.get("items") or []
    else:
        login_required = False
        rows = raw or []

    results = []
    for item in rows[:limit]:
        result = _common.make_result(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("snippet", ""),
            score=item.get("score"),
            published=item.get("published", ""),
        )
        result["engagement"] = {
            "likes": item.get("likes"),
            "comments": item.get("comments"),
            "saves": item.get("saves"),
            "shares": item.get("shares"),
            "views": item.get("views"),
        }
        if item.get("account"):
            result["account"] = item["account"]
        if item.get("author"):
            result["author"] = item["author"]
        _common.fill_identity(result, canonical)
        results.append(result)

    envelope = _common.make_envelope(query, platform or canonical, f"cdp:{canonical}", results)
    if login_required:
        # Surface a clear, actionable signal instead of a silent empty result.
        envelope["login_required"] = True
        envelope["reason"] = (
            f"{canonical} requires being logged in to show search results. "
            f"Log into {canonical} in the browser you enabled for CDP, then retry."
        )
    return envelope


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="CDP platform search (小红书/知乎/微信公众号/豆瓣/虎扑)")
    parser.add_argument("--query", required=True, help="search keyword")
    parser.add_argument("--platform", required=True,
                        help="xiaohongshu | zhihu | weixin | douban | hupu (aliases ok)")
    parser.add_argument("--limit", type=int, default=10, help="max results")
    parser.add_argument("--output", default="", help="write JSON here instead of stdout")
    parser.add_argument("--consent", action="store_true",
                        help="confirm consent to drive your real logged-in browser (required)")
    args = parser.parse_args(argv)

    try:
        envelope = search(args.query, limit=args.limit, platform=args.platform,
                          consent=args.consent)
    except ConsentRequired as exc:
        print(f"Consent required: {exc}", file=sys.stderr)
        return 3
    except CDPError as exc:
        print(f"CDP retrieval unavailable: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"CDP retrieval failed: {exc}", file=sys.stderr)
        return 2

    output = json.dumps(envelope, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Wrote {len(envelope['results'])} results to {args.output}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
