"""JSONL-backed ticket repository implementation."""

import json
import os
from datetime import date, datetime

from ..ports import TicketRepository


class JsonlTicketRepository(TicketRepository):
    def in_period(self, start: date, end: date) -> list[dict]:
        selected = []
        with open(os.environ.get("TICKETS_FILE", "/data/tickets.jsonl"), encoding="utf-8") as file:
            for line in file:
                ticket = json.loads(line)
                day = datetime.fromisoformat(ticket["created_at"]).date()
                if start <= day <= end:
                    selected.append(ticket)
        return selected
