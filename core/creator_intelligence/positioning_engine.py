from __future__ import annotations


class CreatorPositioningEngine:
    def __init__(self, storage):
        self.storage = storage

    def build_offer(self, suggestion: dict) -> dict:
        pain_category = str(suggestion.get("pain_category", "")).strip() or "inconsistent_income"
        price_range = str(suggestion.get("estimated_price_range", "")).strip()

        templates = {
            "pricing": {
                "headline": "Cobra bien sin adivinar: tu rate en 5 minutos",
                "core_promise": "Define una tarifa clara, defendible y rentable en minutos.",
                "who_its_for": "Creadores freelance o content creators que dudan al poner precio a su trabajo.",
                "whats_inside": [
                    "Calculadora rápida de rate por tipo de entrega",
                    "Tabla de ajustes por uso, plazos y complejidad",
                    "Mini guía para justificar tu precio sin fricción",
                ],
                "outcomes": [
                    "Responder precios con seguridad y rapidez",
                    "Evitar infracobrar por miedo o improvisación",
                    "Cerrar deals con márgenes más sanos",
                ],
                "objections": [
                    "No sé si mi nicho soporta ese precio",
                    "Siento que aún no tengo suficiente autoridad",
                    "Me cuesta defender el fee cuando me presionan",
                ],
                "faq": [
                    {"q": "¿Sirve si estoy empezando?", "a": "Sí. Incluye una base por etapas para que cobres según nivel y objetivo."},
                    {"q": "¿Es solo para Instagram/TikTok?", "a": "No. Está pensado para cualquier creador que venda entregables o colaboraciones."},
                ],
                "price_anchor": "Si un solo deal bien cobrado te deja $500 extra, esto se paga solo.",
            },
            "negotiation": {
                "headline": "El guión exacto para negociar sin sonar desesperado",
                "core_promise": "Negocia con estructura clara para proteger tu fee sin quemar oportunidades.",
                "who_its_for": "Creadores que reciben ofertas pero ceden precio o condiciones demasiado rápido.",
                "whats_inside": [
                    "Scripts listos para responder ofertas bajas",
                    "Plantillas de contraoferta por email/DM",
                    "Checklist de términos clave antes de aceptar",
                ],
                "outcomes": [
                    "Mejores condiciones sin fricción innecesaria",
                    "Más control sobre alcance y revisiones",
                    "Más ingresos por acuerdo cerrado",
                ],
                "objections": [
                    "No quiero perder la oportunidad por negociar",
                    "No sé qué decir cuando me piden descuento",
                    "Me incomoda hablar de dinero",
                ],
                "faq": [
                    {"q": "¿Y si la marca dice que no hay presupuesto?", "a": "Tendrás respuestas para mantener valor o reducir alcance sin regalar trabajo."},
                    {"q": "¿Funciona en español?", "a": "Sí. Los guiones están redactados en español directo y adaptable."},
                ],
                "price_anchor": "Si mejoras una negociación en $300, recuperas esta compra al instante.",
            },
            "brand_deals": {
                "headline": "Pitch Deck que te consigue respuestas (y te sube el fee)",
                "core_promise": "Presenta tu propuesta con claridad comercial para convertir más outreach en conversaciones.",
                "who_its_for": "Creadores que envían propuestas a marcas y reciben pocos "
                "respuestas o propuestas débiles.",
                "whats_inside": [
                    "Estructura de deck enfocada en decisión de marca",
                    "Bloques de credibilidad y propuesta de valor",
                    "Template editable para adaptar en 20 minutos",
                ],
                "outcomes": [
                    "Más respuestas a tus pitches",
                    "Percepción de mayor profesionalismo",
                    "Mejor base para negociar fee",
                ],
                "objections": [
                    "No tengo métricas enormes aún",
                    "No sé cómo empaquetar lo que ofrezco",
                    "Mi deck actual se siente genérico",
                ],
                "faq": [
                    {"q": "¿Necesito diseño avanzado?", "a": "No. El enfoque está en mensaje y estructura que vende."},
                    {"q": "¿Incluye ejemplos?", "a": "Sí, con bloques para adaptar a distintos nichos."},
                ],
                "price_anchor": "Si un deck mejor te consigue un deal adicional, el retorno suele ser múltiple.",
            },
            "retainers": {
                "headline": "Convierte deals sueltos en ingresos mensuales (retainers)",
                "core_promise": "Transforma colaboraciones puntuales en acuerdos recurrentes con propuesta clara.",
                "who_its_for": "Creadores con deals esporádicos que quieren estabilidad mensual.",
                "whats_inside": [
                    "Modelo de oferta retainer por niveles",
                    "Guión para transición de one-off a mensual",
                    "Plantilla de alcance, límites y renovaciones",
                ],
                "outcomes": [
                    "Ingresos más previsibles",
                    "Menos tiempo vendiendo cada semana",
                    "Relaciones más duraderas con clientes",
                ],
                "objections": [
                    "No sé si me van a aceptar mensualidad",
                    "Me cuesta definir qué incluir cada mes",
                    "Temo sobrecargarme de trabajo",
                ],
                "faq": [
                    {"q": "¿Y si solo tengo clientes pequeños?", "a": "Incluye versiones livianas para empezar con retainers accesibles."},
                    {"q": "¿Cómo evitar scope creep?", "a": "Con límites y cláusulas simples que ya vienen en la plantilla."},
                ],
                "price_anchor": "Si conviertes un solo cliente a mensual, el impacto anual puede ser enorme.",
            },
            "inconsistent_income": {
                "headline": "Estabiliza ingresos: sistema simple para creadores",
                "core_promise": "Ordena tu oferta comercial para reducir meses flojos y sostener ingresos.",
                "who_its_for": "Creadores con ingresos irregulares que necesitan una base más predecible.",
                "whats_inside": [
                    "Sistema semanal de pipeline comercial",
                    "Plantilla de oferta principal y upsells",
                    "Rutina de seguimiento para no perder leads",
                ],
                "outcomes": [
                    "Más consistencia en ventas mensuales",
                    "Menos dependencia de suerte o viralidad",
                    "Mayor claridad de prioridades comerciales",
                ],
                "objections": [
                    "No tengo tiempo para montar sistemas complejos",
                    "Siento que mi situación cambia cada mes",
                    "No sé por dónde empezar",
                ],
                "faq": [
                    {"q": "¿Cuánto tarda implementarlo?", "a": "Puedes activarlo en una tarde y ejecutarlo por bloques semanales."},
                    {"q": "¿Sirve para varios nichos?", "a": "Sí, el framework es agnóstico y adaptable."},
                ],
                "price_anchor": "Si estabilizas incluso un mes flojo, el retorno supera por mucho el costo.",
            },
        }

        template = templates.get(pain_category, templates["inconsistent_income"])
        suggested_price = self._format_price_range(price_range)

        return {
            "suggestion_id": suggestion.get("id"),
            "pain_category": pain_category,
            "monetization_level": suggestion.get("monetization_level", "low"),
            "headline": template["headline"],
            "subheadline": suggestion.get("positioning_angle") or None,
            "core_promise": template["core_promise"],
            "who_its_for": template["who_its_for"],
            "whats_inside": template["whats_inside"],
            "outcomes": template["outcomes"],
            "objections": template["objections"],
            "faq": template["faq"],
            "price_anchor": template["price_anchor"],
            "suggested_price": suggested_price,
        }

    def _format_price_range(self, raw_range: str) -> str:
        if not raw_range:
            return "$29–$59"
        normalized = raw_range.replace(" ", "")
        if "-" in normalized:
            low, high = normalized.split("-", 1)
            return f"${low}–${high}"
        if normalized.startswith("$"):
            return normalized
        return f"${normalized}"
