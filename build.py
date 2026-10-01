# -*- coding: utf-8 -*-
"""
馬のかまくら サイト生成スクリプト

使い方:
    「更新する.bat」をダブルクリック（または python build.py）

_src フォルダの中身から、サイトの HTML を全部作り直します。
  _src/layout.html        … 全ページ共通の枠（ヘッダー・メニュー）
  _src/home.md            … トップページの本文
  _src/posts/<カテゴリ>/  … 記事（1記事 = 1ファイル）

※ index.html / diary.html / anime.html / games.html と各記事の .html は
   このスクリプトが毎回上書きします。直接編集しないでください。
"""

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "_src"

SITE_NAME = "馬のかまくら"
SITE_DESCRIPTION = "「馬のかまくら」は、アニメ、ゲーム、日々考えたことなどを適当に書いている個人サイトです。"

# 隠しページのファイル名（推測されにくい名前にしています。変えてもOK）
SECRET_FILE = "kamakura-no-oku.html"

# トップページの「お知らせ」に出す件数
NEWS_COUNT = 10

# カテゴリの設定（並び順がメニューの順番になります）
# カテゴリを増やしたいときは、ここに1行足して _src/posts/ に同じ名前のフォルダを作るだけ
CATEGORIES = [
    # (フォルダ名, メニュー表示名, 一覧ページの説明文)
    ("diary", "DIARY", "日々思ったこと、考えたこと。"),
    ("anime", "ANIME", "心に残った作品、キャラクター、これから楽しみな作品。"),
    ("games", "GAMES", "遊んだゲーム、考えたこと、そして勝負の記録。"),
]


# ---------------------------------------------------------------
# 本文の変換（かんたん記法 → HTML）
# ---------------------------------------------------------------

BLOCK_TAG = re.compile(r"^\s*<(div|ul|ol|img|iframe|table|blockquote|figure|h[1-6]|p|hr|section)\b", re.I)


YOUTUBE = re.compile(
    r"^\s*https?://(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/|embed/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})\S*\s*$")


def youtube_embed(video_id):
    return (f'<div class="video"><iframe src="https://www.youtube-nocookie.com/embed/{video_id}" '
            f'title="YouTube動画" loading="lazy" '
            f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
            f'referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe></div>')


def inline(text):
    # [表示する文字](URL) → リンク
    def link(m):
        label, url = m.group(1), m.group(2)
        if url.startswith("http"):
            return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'
        return f'<a href="{url}">{label}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    # **太字**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return text


def render_body(text, heading_tag="h4"):
    """空行で段落を区切り、段落内の改行は <br> にする。HTMLもそのまま書ける。"""
    out = []
    for block in re.split(r"\n[ \t]*\n", text.strip("\n")):
        if not block.strip():
            continue
        yt = YOUTUBE.match(block)
        if yt:
            out.append(youtube_embed(yt.group(1)))
        elif block.startswith("## "):
            out.append(f"<{heading_tag}>{inline(block[3:].strip())}</{heading_tag}>")
        elif BLOCK_TAG.match(block):
            out.append(block)
        else:
            lines = [inline(line.rstrip()) for line in block.split("\n")]
            out.append("<p>\n" + "<br>\n".join(lines) + "\n</p>")
    return "\n\n".join(out)


def plain_summary(text, length=110):
    t = "\n".join(l for l in text.split("\n") if not YOUTUBE.match(l))
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"[\s　*#]+", " ", t).strip()
    return t[:length] + ("…" if len(t) > length else "")


# ---------------------------------------------------------------
# 記事の読み込み
# ---------------------------------------------------------------

def read_source(path):
    raw = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    meta = {}
    body = raw
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", raw, re.S)
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = m.group(2)
    # 「//」で始まる行はメモ扱いで、ページには出さない
    body = "\n".join(l for l in body.split("\n") if not l.lstrip().startswith("//"))
    return meta, body


def load_posts(errors):
    posts = []
    for key, label, _ in CATEGORIES:
        folder = SRC / "posts" / key
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md")):
            meta, body = read_source(path)
            if meta.get("draft", "").lower() in ("yes", "true", "1", "はい"):
                continue
            date = meta.get("date", "")
            if not re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", date):
                errors.append(f"{path.relative_to(ROOT)}: date の書き方が違います（例: date: 2026-10-01）")
                continue
            y, mo, d = (int(x) for x in date.split("-"))
            posts.append({
                "category": key,
                "category_label": label,
                "title": meta.get("title") or path.stem,
                "date": (y, mo, d),
                "date_dot": f"{y}.{mo:02d}.{d:02d}",
                "date_short": f"{y}.{mo}.{d}",
                "official": meta.get("official", ""),
                "body": body,
                "file": path.stem + ".html",
            })
    return posts


# ---------------------------------------------------------------
# ページ組み立て
# ---------------------------------------------------------------

def nav_html(active):
    items = [("index.html", "HOME", "home")] + [(f"{k}.html", lbl, k) for k, lbl, _ in CATEGORIES]
    links = []
    for href, label, key in items:
        mark = "❅" if key == active else "✦"
        links.append(f'        <a href="{href}">{mark} {label}</a>')
    return "\n".join(links)


def render_page(layout, *, title, description, active, content, body_class="", head_extra=""):
    page = layout
    for k, v in {
        "{{head_extra}}": head_extra,
        "{{secret_url}}": SECRET_FILE,
        "{{title}}": html.escape(title),
        "{{description}}": html.escape(description),
        "{{nav}}": nav_html(active),
        "{{content}}": content,
        "{{body_class}}": body_class,
    }.items():
        page = page.replace(k, v)
    return page


def build_post(layout, post, prev_post, next_post, intro):
    official = ""
    if post["official"]:
        official = (f'<p class="official-link"><a href="{post["official"]}" target="_blank" '
                    f'rel="noopener noreferrer">作品公式サイト</a></p>\n\n')
    pager = []
    if prev_post:
        pager.append(f'<a class="pager-prev" href="{prev_post["file"]}">← {html.escape(prev_post["title"])}</a>')
    pager.append(f'<a class="pager-list" href="{post["category"]}.html">一覧へ戻る</a>')
    if next_post:
        pager.append(f'<a class="pager-next" href="{next_post["file"]}">{html.escape(next_post["title"])} →</a>')

    content = f"""<main class="content">

<h2>{post["category_label"]}</h2>

<p class="intro">{intro}</p>

<article class="diary-entry">

    <p class="diary-date">{post["date_dot"]}</p>

    <h3>{html.escape(post["title"])}</h3>

    <div class="diary-body">
{official}{render_body(post["body"])}
    </div>

</article>

<nav class="pager">
    {(chr(10) + "    ").join(pager)}
</nav>

</main>"""
    return render_page(layout,
                       title=f'{post["title"]} - {SITE_NAME}',
                       description=plain_summary(post["body"]),
                       active=post["category"],
                       content=content)


def build_list(layout, key, label, intro, posts):
    if posts:
        items = "\n".join(
            f'    <li><a href="{p["file"]}"><span class="post-date">{p["date_dot"]}</span>'
            f'<span class="post-title">{html.escape(p["title"])}</span></a></li>'
            for p in posts)
        listing = f'<ul class="post-list">\n{items}\n</ul>'
    else:
        listing = '<p class="empty">今後追加予定</p>'
    content = f"""<main class="content">

<h2>{label}</h2>

<p class="intro">{intro}</p>

{listing}

</main>"""
    return render_page(layout, title=f"{label} - {SITE_NAME}", description=intro,
                       active=key, content=content)


def build_home(layout, posts):
    meta, body = read_source(SRC / "home.md")
    news = "\n".join(
        f'<strong>{p["date_short"]}</strong><br> {p["category_label"]}に'
        f'「<a href="{p["file"]}">{html.escape(p["title"])}</a>」を投稿しました。<br>'
        for p in posts[:NEWS_COUNT])
    content = render_body(body, heading_tag="h2").replace("<p>\n{{news}}\n</p>", f"<p class=\"news\">\n{news}\n</p>")
    return render_page(layout,
                       title=meta.get("title", SITE_NAME),
                       description=SITE_DESCRIPTION,
                       active="home",
                       content=content,
                       body_class="home")


def build_secret(layout):
    meta, body = read_source(SRC / "secret.md")
    content = f"""<main class="content secret-room">

<h2>{html.escape(meta.get("heading", "SECRET"))}</h2>

<p class="intro">{html.escape(meta.get("intro", ""))}</p>

<article class="secret-body">
{render_body(body)}
</article>

<p class="secret-exit"><a href="index.html">❅ 外の世界へ戻る</a></p>

</main>"""
    return render_page(layout,
                       title=meta.get("title", f"??? - {SITE_NAME}"),
                       description="",
                       active="",
                       content=content,
                       body_class="secret",
                       head_extra='    <meta name="robots" content="noindex, nofollow">')


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    errors = []
    layout = (SRC / "layout.html").read_text(encoding="utf-8-sig")
    posts = load_posts(errors)

    # 同じファイル名の記事がないかチェック
    seen = {}
    for p in posts:
        if p["file"] in seen:
            errors.append(f'ファイル名が重複しています: {p["file"]}')
        seen[p["file"]] = p

    written = []

    def write(name, text):
        (ROOT / name).write_text(text, encoding="utf-8", newline="\n")
        written.append(name)

    # 新しい順
    newest_first = sorted(posts, key=lambda p: (p["date"], p["file"]), reverse=True)

    write("index.html", build_home(layout, newest_first))

    if (SRC / "secret.md").exists():
        write(SECRET_FILE, build_secret(layout))

    for key, label, intro in CATEGORIES:
        cat_posts = [p for p in newest_first if p["category"] == key]
        write(f"{key}.html", build_list(layout, key, label, intro, cat_posts))
        oldest_first = list(reversed(cat_posts))
        for i, post in enumerate(oldest_first):
            prev_post = oldest_first[i - 1] if i > 0 else None
            next_post = oldest_first[i + 1] if i + 1 < len(oldest_first) else None
            write(post["file"], build_post(layout, post, prev_post, next_post, intro))

    print(f"完了: {len(written)} ページを作成しました（記事 {len(posts)} 件）")
    for p in newest_first:
        print(f'  {p["date_dot"]}  [{p["category_label"]}] {p["title"]}  → {p["file"]}')
    if errors:
        print("\n⚠ 確認してください:")
        for e in errors:
            print("  - " + e)


if __name__ == "__main__":
    main()
