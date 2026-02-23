from __future__ import annotations


def to_gumroad_markdown(offer: dict) -> str:
    headline = str(offer.get("headline", "Oferta para creadores")).strip()
    who_its_for = str(offer.get("who_its_for", "")).strip()
    core_promise = str(offer.get("core_promise", "")).strip()
    whats_inside = offer.get("whats_inside") or []
    outcomes = offer.get("outcomes") or []
    faq_items = offer.get("faq") or []
    price_anchor = str(offer.get("price_anchor", "")).strip()
    suggested_price = str(offer.get("suggested_price", "")).strip()

    lines: list[str] = [
        f"# {headline}",
        "",
        "## Para quién es",
        who_its_for,
        "",
        "## Qué resuelve",
        core_promise,
        "",
        "## Qué incluye",
    ]

    lines.extend(f"- {item}" for item in whats_inside)
    lines.extend([
        "",
        "## Resultados",
    ])
    lines.extend(f"- {item}" for item in outcomes)
    lines.extend([
        "",
        "## FAQ",
    ])

    for item in faq_items:
        question = str(item.get("q", "")).strip()
        answer = str(item.get("a", "")).strip()
        if question:
            lines.append(f"**{question}**")
            if answer:
                lines.append(answer)
            lines.append("")

    cta_line = "Si esto encaja con tu momento, empieza hoy y aplícalo esta misma semana."
    if suggested_price:
        cta_line = f"Si esto encaja con tu momento, empieza hoy por {suggested_price} y aplícalo esta misma semana."

    lines.extend([
        "## Cierre",
        cta_line,
    ])
    if price_anchor:
        lines.append(price_anchor)

    return "\n".join(lines).strip() + "\n"
