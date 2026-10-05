import re

import nh3
from django import template
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt

register = template.Library()
markdown = MarkdownIt("commonmark", {"html": False}).disable(["image", "link", "autolink"])


@register.simple_tag
def blocks(blocks, item, usage):
    assets = {a.local_asset_id: a for a in item.revision.assets.filter(usage=usage)}
    output = []
    for block in blocks:
        if block["type"] == "image":
            ref = assets[block["asset_id"]]
            if usage == "choice":
                output.append(
                    format_html(
                        '<img src="/image/{}/{}/" alt="{}" width="{}" height="{}">',
                        item.pk,
                        ref.pk,
                        block["alt"],
                        ref.asset.width,
                        ref.asset.height,
                    )
                )
            else:
                output.append(
                    format_html(
                        '<button class="figure" type="button" aria-label="図を拡大: {}"><img src="/image/{}/{}/" alt="{}" width="{}" height="{}"></button>',
                        block["alt"],
                        item.pk,
                        ref.pk,
                        block["alt"],
                        ref.asset.width,
                        ref.asset.height,
                    )
                )
        else:
            # Keep TeX out of Markdown's escaping rules; both halves are escaped/sanitized.
            pieces = re.split(r"(\$\$[\s\S]*?\$\$|\$[^$\n]+?\$)", block["text"])
            math = {}
            for i in range(1, len(pieces), 2):
                key = f"MATHPLACEHOLDER{i}END"
                math[key] = str(escape(pieces[i]))
                pieces[i] = key
            html = nh3.clean(
                markdown.render("".join(pieces)),
                tags={
                    "p",
                    "strong",
                    "em",
                    "ul",
                    "ol",
                    "li",
                    "code",
                    "pre",
                    "blockquote",
                    "br",
                    "hr",
                    "h2",
                    "h3",
                },
                attributes={},
            )
            for key, value in math.items():
                html = html.replace(key, value)
            output.append(mark_safe('<div class="prose">' + html + "</div>"))
    return mark_safe("".join(map(str, output)))
