"""Stable application contracts implemented by infrastructure adapters."""

from datetime import date
from typing import Iterator, Protocol


class TextGenerationGateway(Protocol):
    def generate(self, capability: str, task: str, content: str) -> str: ...
    def stream(self, capability: str, task: str, content: str) -> Iterator[str]: ...


class TicketRepository(Protocol):
    def in_period(self, start: date, end: date) -> list[dict]: ...
