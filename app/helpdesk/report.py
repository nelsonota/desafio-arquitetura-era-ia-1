import json

from fastapi import HTTPException

from .ports import TextGenerationGateway, TicketRepository
from .schemas import PeriodInput, Topic, TopicsReport

TICKETS_PER_CALL = 150


def topics(period: PeriodInput, gateway: TextGenerationGateway,
           ticket_repository: TicketRepository) -> TopicsReport:
    if period.start > period.end:
        raise HTTPException(status_code=422, detail="A data inicial é posterior à data final")

    selected = ticket_repository.in_period(period.start, period.end)
    totals: dict[str, dict] = {}
    for first in range(0, len(selected), TICKETS_PER_CALL):
        batch = selected[first:first + TICKETS_PER_CALL]
        content = "\n".join(f"[{ticket['id']}] {ticket['text']}" for ticket in batch)
        text = gateway.generate("ticket-topics", "topics", content)
        try:
            answer = json.loads(text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=502, detail="Resposta inválida do modelo") from exc
        for item in answer["topics"]:
            current = totals.setdefault(item["topic"], {"count": 0, "examples": []})
            current["count"] += item["count"]
            current["examples"] = (current["examples"] + item["examples"])[:3]

    items = [Topic(topic=name, **data) for name, data in totals.items()]
    items.sort(key=lambda topic: (-topic.count, topic.topic))
    return TopicsReport(start=period.start, end=period.end, total_tickets=len(selected), topics=items)
