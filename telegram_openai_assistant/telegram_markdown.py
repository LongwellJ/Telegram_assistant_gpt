"""Converts the model's CommonMark-style Markdown output into Telegram's HTML
parse-mode format, so **bold**, _italic_, `code`, links, lists, and blockquotes
actually render instead of showing up as raw markdown syntax in the chat."""

import html as _html

from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark").enable("strikethrough")


def _escape(text: str) -> str:
    return _html.escape(text, quote=False)


def _render_inline(children) -> str:
    out = []
    for tok in children:
        t = tok.type
        if t == "text":
            out.append(_escape(tok.content))
        elif t == "code_inline":
            out.append(f"<code>{_escape(tok.content)}</code>")
        elif t == "strong_open":
            out.append("<b>")
        elif t == "strong_close":
            out.append("</b>")
        elif t == "em_open":
            out.append("<i>")
        elif t == "em_close":
            out.append("</i>")
        elif t == "s_open":
            out.append("<s>")
        elif t == "s_close":
            out.append("</s>")
        elif t == "link_open":
            href = _html.escape(tok.attrGet("href") or "", quote=True)
            out.append(f'<a href="{href}">')
        elif t == "link_close":
            out.append("</a>")
        elif t in ("softbreak", "hardbreak"):
            out.append("\n")
        elif t == "image":
            out.append(_escape(tok.content or tok.attrGet("alt") or ""))
        elif tok.children:
            out.append(_render_inline(tok.children))
        elif tok.content:
            out.append(_escape(tok.content))
    return "".join(out)


def to_telegram_html(text: str) -> str:
    """Renders Markdown to the subset of HTML Telegram's parse_mode="HTML" accepts
    (b/i/s/code/pre/a/blockquote). Anything not explicitly handled (raw HTML blocks,
    tables, etc.) is dropped rather than passed through, so we never emit an entity
    Telegram doesn't recognize."""
    tokens = _md.parse(text)
    out = []
    list_stack = []  # each entry: ["bullet"|"ordered", count]

    for tok in tokens:
        t = tok.type

        if t == "heading_open":
            out.append("<b>")
        elif t == "heading_close":
            out.append("</b>\n\n")
        elif t == "inline":
            out.append(_render_inline(tok.children))
        elif t == "paragraph_close":
            # Inside a list item, markdown-it wraps content in a paragraph even for
            # "tight" lists in some cases; list_item_close already adds the newline,
            # so skip the extra blank line here to avoid a gap between every bullet.
            if not list_stack:
                out.append("\n\n")
        elif t == "bullet_list_open":
            list_stack.append(["bullet", 0])
        elif t == "ordered_list_open":
            start = int(tok.attrGet("start") or 1)
            list_stack.append(["ordered", start - 1])
        elif t in ("bullet_list_close", "ordered_list_close"):
            list_stack.pop()
            if not list_stack:
                out.append("\n")
        elif t == "list_item_open":
            depth = max(len(list_stack) - 1, 0)
            indent = "  " * depth
            if list_stack and list_stack[-1][0] == "ordered":
                list_stack[-1][1] += 1
                out.append(f"{indent}{list_stack[-1][1]}. ")
            else:
                out.append(f"{indent}• ")
        elif t == "list_item_close":
            out.append("\n")
        elif t == "blockquote_open":
            out.append("<blockquote>")
        elif t == "blockquote_close":
            out.append("</blockquote>\n\n")
        elif t in ("code_block", "fence"):
            out.append(f"<pre>{_escape(tok.content)}</pre>\n\n")
        elif t == "hr":
            out.append("─" * 10 + "\n\n")
        # Anything else (html_block, tables, etc.) is intentionally skipped.

    result = "".join(out).strip()
    result = result.replace("\n\n</blockquote>", "</blockquote>")
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")
    return result
