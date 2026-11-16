from .ports import TextGenerationGateway
from .schemas import ReplySuggestion, TicketInput


def suggest(ticket: TicketInput, gateway: TextGenerationGateway) -> ReplySuggestion:
    text = gateway.generate("reply-suggestion", "suggest", ticket.text)
    return ReplySuggestion(ticket_id=ticket.ticket_id, suggestion=text)
