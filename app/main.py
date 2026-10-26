
import os
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import select

from database import make_engine, init_database
from schedule_repository import ScheduleRepository
from approval_service import ApprovalService
from ai_scheduler import AIScheduler
from models import ScheduleProposalDB

from app.schemas import (
    ScheduleCreate,
    ScheduleUpdate,
    AIInstruction,
    ApprovalRequest,
)

from schedule_policy import (
    ScheduleConflictError,
    ScheduleValidationError,
)


def serialize_event(event):
    return {
        "id": event.id,
        "title": event.title,
        "date": event.event_date.isoformat(),
        "start": event.start_time,
        "end": event.end_time,
        "category": event.category,
    }


def create_app(
    database_url: str | None = None,
    parser=None,
) -> FastAPI:
    """
    Create an independent FastAPI application.

    database_url:
        Custom database for testing/development.

    parser:
        Optional injected parser for tests.
        Defaults to the real Ollama CommandParser.
    """

    db_url = database_url or os.getenv(
        "DATABASE_URL",
        "sqlite:///scheduler.db",
    )

    engine = make_engine(db_url)
    repository = ScheduleRepository(engine)

    approval_service = ApprovalService(
        engine,
        preferences=repository.preferences,
    )

    ai_scheduler = AIScheduler(
        repository=repository,
        parser=parser,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_database(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title="AI Smart Scheduler API",
        description="Personalized AI Scheduling Backend",
        version="0.2.0",
        lifespan=lifespan,
    )

    # Application-scoped services.
    app.state.repository = repository
    app.state.approval_service = approval_service
    app.state.ai_scheduler = ai_scheduler

    @app.get("/")
    def root():
        return {
            "name": "AI Smart Scheduler API",
            "version": "0.2.0",
            "documentation": "/docs",
        }

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "ai-smart-scheduler",
        }

    @app.get("/schedules")
    def list_schedules(event_date: date = Query(...)):
        events = repository.list_events(event_date)

        return {
            "date": event_date.isoformat(),
            "events": [
                serialize_event(event)
                for event in events
            ],
        }

    @app.post("/schedules", status_code=201)
    def create_schedule(payload: ScheduleCreate):
        try:
            event = repository.create_event(
                title=payload.title,
                event_date=payload.event_date,
                start_time=payload.start_time,
                end_time=payload.end_time,
                category=payload.category,
            )
        except ScheduleConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc
        except (ScheduleValidationError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        return serialize_event(event)

    @app.post("/ai/schedule")
    def propose_schedule(payload: AIInstruction):
        try:
            result = ai_scheduler.process(
                payload.instruction
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        if result["status"] != "pending_approval":
            return result

        saved = approval_service.save_proposal(
            payload.instruction,
            result,
        )

        return {
            **result,
            "proposal_id": saved["proposal_id"],
            "options": saved["options"],
        }
        
    
    @app.get("/schedules/{event_id}")
    def get_schedule(event_id: int):
        event = repository.get_event(event_id)

        if event is None:
            raise HTTPException(
                status_code=404,
                detail="Schedule not found",
            )

        return serialize_event(event)

    @app.patch("/schedules/{event_id}")
    def update_schedule(
        event_id: int,
        payload: ScheduleUpdate,
    ):
        changes = payload.model_dump(
            exclude_unset=True
        )

        if not changes:
            raise HTTPException(
                status_code=422,
                detail="At least one field is required",
            )

        if any(value is None for value in changes.values()):
            raise HTTPException(
                status_code=422,
                detail="Null values are not allowed",
            )

        try:
            event = repository.update_event(
                event_id, changes
            )
        except ScheduleConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc
        except (ScheduleValidationError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        if event is None:
            raise HTTPException(
                status_code=404,
                detail="Schedule not found",
            )

        return serialize_event(event)

    @app.delete("/schedules/{event_id}", status_code=204)
    def delete_schedule(event_id: int):
        deleted = repository.delete_event(event_id)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Schedule not found",
            )

        return None

    @app.get("/proposals/{proposal_id}")
    def get_proposal(proposal_id: int):
        with approval_service.Session() as session:
            proposal = session.get(
                ScheduleProposalDB,
                proposal_id,
            )

            if proposal is None:
                raise HTTPException(
                    status_code=404,
                    detail="Proposal not found",
                )

            return {
                "id": proposal.id,
                "title": proposal.title,
                "date": proposal.event_date.isoformat(),
                "duration_minutes": proposal.duration_minutes,
                "status": proposal.status,
                "approved_option_id": (
                    proposal.approved_option_id
                ),
                "options": [
                    {
                        "id": option.id,
                        "start": option.start_time,
                        "end": option.end_time,
                        "score": option.score,
                    }
                    for option in proposal.options
                ],
            }

    @app.post("/proposals/{proposal_id}/approve")
    def approve_proposal(
        proposal_id: int,
        payload: ApprovalRequest,
    ):
        result = approval_service.approve(
            proposal_id=proposal_id,
            option_id=payload.option_id,
        )

        status = result["status"]

        if status == "not_found":
            raise HTTPException(
                status_code=404,
                detail=result,
            )

        if status == "invalid_option":
            raise HTTPException(
                status_code=400,
                detail=result,
            )

        if status in {
            "already_processed",
            "conflict_or_invalid",
        }:
            raise HTTPException(
                status_code=409,
                detail=result,
            )

        return result

    return app


# Uvicorn entry point.
app = create_app()
