from __future__ import annotations


class DraftAssetExecutor:
    name = "draft_asset_executor"
    supported_types = ["draft_asset"]

    def execute(self, action: dict, context: dict) -> dict:
        target_id = str(action.get("target_id") or "audience")
        reasoning = str(action.get("reasoning") or "Generar un borrador útil")
        prompt = str(context.get("prompt") or "")

        title = f"Borrador para {target_id}"
        body = "\n".join(
            [
                f"Objetivo: {reasoning}.",
                f"Contexto: {prompt or 'sin contexto adicional' }.",
                "Checklist:",
                "1. Mensaje principal claro.",
                "2. Beneficio tangible para el usuario.",
                "3. Llamado a la acción medible.",
            ]
        )

        return {
            "artifact_type": "text_draft",
            "title": title,
            "content": body,
        }
