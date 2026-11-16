import json
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException

from .ports import TextGenerationGateway, TicketRepository
from .schemas import PeriodInput, Topic, TopicsReport

TICKETS_PER_CALL = 150


def topics(period: PeriodInput, gateway: TextGenerationGateway,
           ticket_repository: TicketRepository) -> TopicsReport:
    if period.start > period.end:
        raise HTTPException(status_code=422, detail="A data inicial é posterior à data final")

    selected = ticket_repository.in_period(period.start, period.end)
    batches = [selected[first:first + TICKETS_PER_CALL]
               for first in range(0, len(selected), TICKETS_PER_CALL)]

    def generate(batch):
        content = "\n".join(f"[{ticket['id']}] {ticket['text']}" for ticket in batch)
        return gateway.generate("ticket-topics", "topics", content)

    with ThreadPoolExecutor(max_workers=20) as executor:
        answers = list(executor.map(generate, batches))

    totals: dict[str, dict] = {}
    for text in answers:
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
