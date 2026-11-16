from collections.abc import Iterator

from .ports import TextGenerationGateway
from .schemas import ReplySuggestion, TicketInput


def suggest(ticket: TicketInput, gateway: TextGenerationGateway) -> ReplySuggestion:
    text = gateway.generate("reply-suggestion", "suggest", ticket.text)
    return ReplySuggestion(ticket_id=ticket.ticket_id, suggestion=text)


def suggest_stream(ticket: TicketInput, gateway: TextGenerationGateway) -> Iterator[tuple[str, dict]]:
    emitted = False
    for capability in ("reply-suggestion", "reply-suggestion-tech", "reply-suggestion-mini"):
        try:
            for chunk in gateway.stream(capability, "suggest", ticket.text):
                emitted = True
                yield "message", {"chunk": chunk}
            yield "end", {"ticket_id": ticket.ticket_id}
            return
        except Exception:
            if emitted:
                yield "error", {"ticket_id": ticket.ticket_id, "message": "A geração foi interrompida"}
                return
    yield "error", {"ticket_id": ticket.ticket_id, "message": "A geração foi interrompida"}
