import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse

from . import classification, extraction, report, suggestion
from .adapters.gateway_client import create_gateway_client
from .adapters.ticket_file_repository import JsonlTicketRepository
from .schemas import Classification, OrderData, PeriodInput, TicketInput

app = FastAPI(title="Helpdesk")
gateway = create_gateway_client()
ticket_repository = JsonlTicketRepository()
report_jobs: dict[str, dict] = {}
report_lock = threading.Lock()
report_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="topic-report")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tickets/classification")
def classify_ticket(ticket: TicketInput) -> Classification:
    return classification.classify(ticket, gateway)


@app.post("/tickets/reply-suggestion")
def suggest_reply(ticket: TicketInput):
    def events():
        import json
        for event, data in suggestion.suggest_stream(ticket, gateway):
            encoded = json.dumps(data, ensure_ascii=False)
            if event == "message":
                yield f"data: {encoded}\n\n"
            else:
                yield f"event: {event}\ndata: {encoded}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@app.post("/tickets/extraction")
def extract_order_data(ticket: TicketInput) -> OrderData:
    return extraction.extract(ticket, gateway)


def _run_report(job_id: str, period: PeriodInput):
    with report_lock:
        report_jobs[job_id]["state"] = "running"
    try:
        result = report.topics(period, gateway, ticket_repository)
        with report_lock:
            report_jobs[job_id].update(state="completed", result=result.model_dump(mode="json"))
    except Exception as exc:
        with report_lock:
            report_jobs[job_id].update(state="failed", reason=str(getattr(exc, "detail", exc)))


@app.post("/reports/topics", status_code=202)
def start_topics_report(period: PeriodInput, response: Response):
    if period.start > period.end:
        return JSONResponse(status_code=422, content={"detail": "A data inicial é posterior à data final"})
    job_id = uuid.uuid4().hex
    with report_lock:
        report_jobs[job_id] = {"state": "pending", "period": period}
    report_executor.submit(_run_report, job_id, period)
    response.headers["Location"] = f"/reports/topics/status/{job_id}"
    response.headers["Retry-After"] = "1"
    return {"job_id": job_id, "state": "pending"}


@app.get("/reports/topics/status/{job_id}")
def topics_report_status(job_id: str):
    with report_lock:
        job = report_jobs.get(job_id)
        if not job:
            return JSONResponse(status_code=404, content={"detail": "Relatório não encontrado"})
        if job["state"] == "completed":
            return RedirectResponse(f"/reports/topics/{job_id}", status_code=303)
        if job["state"] == "failed":
            return {"state": "failed", "reason": job["reason"]}
        return {"state": job["state"], "progress": "em processamento"}


@app.get("/reports/topics/{job_id}")
def get_topics_report(job_id: str):
    with report_lock:
        job = report_jobs.get(job_id)
        if not job:
            return JSONResponse(status_code=404, content={"detail": "Relatório não encontrado"})
        if job["state"] == "failed":
            return JSONResponse(status_code=409, content={"state": "failed", "reason": job["reason"]})
        if job["state"] != "completed":
            return JSONResponse(status_code=409, content={"state": job["state"]})
        return job["result"]
