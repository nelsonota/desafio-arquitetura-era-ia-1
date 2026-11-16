import re
import json

from fastapi import HTTPException

from .ports import TextGenerationGateway
from .schemas import OrderData, TicketInput

ORDER_FORMAT = re.compile(r"^#\d{6}$")


def extract(ticket: TicketInput, gateway: TextGenerationGateway) -> OrderData:
    text = gateway.generate("order-extraction", "extract", ticket.text)
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Resposta inválida do modelo") from exc
    order_number = data.get("order_number")
    if order_number is not None and not ORDER_FORMAT.match(order_number):
        raise HTTPException(status_code=502, detail="Número de pedido em formato inválido")
    return OrderData(ticket_id=ticket.ticket_id, order_number=order_number, product=data.get("product"))
