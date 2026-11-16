import json

from fastapi import HTTPException

from .ports import TextGenerationGateway
from .schemas import Classification, TicketInput

CATEGORIES = {"delivery", "payment", "exchange_return", "product_defect", "other"}
PRIORITIES = {"low", "medium", "high"}


def classify(ticket: TicketInput, gateway: TextGenerationGateway) -> Classification:
    text = gateway.generate("ticket-classification", "classify", ticket.text)
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Resposta inválida do modelo") from exc
    if data.get("category") not in CATEGORIES or data.get("priority") not in PRIORITIES:
        raise HTTPException(status_code=502, detail="Classificação fora dos valores permitidos")
    return Classification(ticket_id=ticket.ticket_id, **data)
