from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import ExternalServiceNotConfiguredError, WorkflowNotFoundError


_db: AsyncIOMotorDatabase | None = None


def init_document_store(database: AsyncIOMotorDatabase) -> None:
    global _db
    _db = database


def _database() -> AsyncIOMotorDatabase:
    if _db is None:
        raise ExternalServiceNotConfiguredError("MongoDB document store is not initialized")
    return _db


def _now() -> datetime:
    return datetime.now(UTC)


def _public(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None
    copy = dict(document)
    if "_id" in copy:
        copy["id"] = str(copy["_id"])
        copy.setdefault("workflow_id", str(copy["_id"]) if str(copy["_id"]).startswith("wf_") else copy.get("workflow_id"))
        del copy["_id"]
    return copy


async def create_workflow(workflow: dict) -> str:
    if not workflow.get("user_id"):
        raise ValueError("workflow user_id is required")
    workflow_id = workflow.get("_id") or workflow.get("workflow_id") or f"wf_{uuid4().hex}"
    document = {
        **workflow,
        "_id": workflow_id,
        "workflow_id": workflow_id,
        "created_at": workflow.get("created_at") or _now(),
        "started_at": workflow.get("started_at"),
        "completed_at": workflow.get("completed_at"),
        "results_count": workflow.get("results_count", 0),
        "total_cost_usd": workflow.get("total_cost_usd", 0.0),
        "total_tokens": workflow.get("total_tokens", 0),
    }
    await _database().workflows.insert_one(document)
    return workflow_id


async def update_workflow_status(workflow_id: str, status: str, user_id: str | None = None, **kwargs) -> None:
    query: dict[str, Any] = {"_id": workflow_id}
    if user_id is not None:
        query["user_id"] = user_id
    update = {"status": status, **kwargs}
    if status == "running":
        update.setdefault("started_at", _now())
    if status in {"completed", "failed"}:
        update.setdefault("completed_at", _now())
    result = await _database().workflows.update_one(query, {"$set": update})
    if result.matched_count == 0:
        raise WorkflowNotFoundError(f"Workflow {workflow_id} was not found")


async def get_workflow(workflow_id: str, user_id: str | None = None) -> dict:
    query: dict[str, Any] = {"_id": workflow_id}
    if user_id is not None:
        query["user_id"] = user_id
    workflow = await _database().workflows.find_one(query)
    if not workflow:
        raise WorkflowNotFoundError(f"Workflow {workflow_id} was not found")
    return _public(workflow) or {}


async def save_company(company: dict) -> str:
    if not company.get("user_id"):
        raise ValueError("company user_id is required")
    company_id = company.get("_id") or company.get("id") or f"co_{uuid4().hex}"
    document = {**company, "_id": company_id, "id": company_id, "created_at": company.get("created_at") or _now()}
    await _database().companies.update_one(
        {"_id": company_id, "user_id": company["user_id"]},
        {"$set": document},
        upsert=True,
    )
    return company_id


async def save_contact(contact: dict) -> str:
    if not contact.get("user_id"):
        raise ValueError("contact user_id is required")
    contact_id = contact.get("_id") or contact.get("id") or f"ct_{uuid4().hex}"
    document = {**contact, "_id": contact_id, "id": contact_id, "created_at": contact.get("created_at") or _now()}
    await _database().contacts.update_one(
        {"_id": contact_id, "user_id": contact["user_id"]},
        {"$set": document},
        upsert=True,
    )
    return contact_id


async def update_contact_approval(
    contact_id: str,
    workflow_id: str,
    user_id: str,
    approval_status: str,
    reason: str | None = None,
    edits: dict | None = None,
) -> None:
    update: dict[str, Any] = {"approval_status": approval_status, "approval_updated_at": _now()}
    if reason:
        update["approval_reason"] = reason
    if edits:
        update.update(edits)
        update["edited_at"] = _now()
    result = await _database().contacts.update_one(
        {"_id": contact_id, "workflow_id": workflow_id, "user_id": user_id},
        {"$set": update},
    )
    if result.matched_count == 0:
        raise WorkflowNotFoundError(f"Contact {contact_id} was not found for workflow {workflow_id}")


async def log_agent_event(event: dict) -> str:
    if not event.get("user_id"):
        raise ValueError("agent log user_id is required")
    log_id = event.get("_id") or f"log_{uuid4().hex}"
    document = {**event, "_id": log_id, "timestamp": event.get("timestamp") or _now()}
    await _database().agent_logs.insert_one(document)
    return log_id


async def get_workflow_results(workflow_id: str, user_id: str | None = None) -> dict:
    workflow = await get_workflow(workflow_id, user_id=user_id)
    scoped = {"workflow_id": workflow_id}
    if user_id is not None:
        scoped["user_id"] = user_id
    companies = [_public(doc) async for doc in _database().companies.find(scoped).sort("created_at", 1)]
    contacts = [_public(doc) async for doc in _database().contacts.find(scoped).sort("created_at", 1)]
    logs = [_public(doc) async for doc in _database().agent_logs.find(scoped).sort("timestamp", 1)]
    return {
        "workflow": workflow,
        "companies": [doc for doc in companies if doc],
        "contacts": [doc for doc in contacts if doc],
        "summary_report": workflow.get("summary_report"),
        "logs": [doc for doc in logs if doc],
    }


async def get_user_workflows(user_id: str, page: int, per_page: int, status_filter: str | None = None) -> dict:
    page = max(page, 1)
    per_page = min(max(per_page, 1), 100)
    skip = (page - 1) * per_page
    query: dict[str, Any] = {"user_id": user_id}
    if status_filter:
        query["status"] = status_filter
    total = await _database().workflows.count_documents(query)
    cursor = _database().workflows.find(query).sort("created_at", -1).skip(skip).limit(per_page)
    workflows = [_public(doc) async for doc in cursor]
    return {"workflows": [doc for doc in workflows if doc], "total": total, "page": page, "per_page": per_page}


async def get_agent_logs(
    user_id: str,
    agent_id: str,
    workflow_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    query: dict[str, Any] = {"user_id": user_id, "agent_name": agent_id}
    if workflow_id:
        query["workflow_id"] = workflow_id
    total = await _database().agent_logs.count_documents(query)
    cursor = _database().agent_logs.find(query).sort("timestamp", -1).skip(offset).limit(min(limit, 200))
    logs = [_public(doc) async for doc in cursor]
    return {"logs": [doc for doc in logs if doc], "total": total}


async def delete_workflow(workflow_id: str, user_id: str) -> None:
    query = {"workflow_id": workflow_id, "user_id": user_id}
    workflow_result = await _database().workflows.delete_one({"_id": workflow_id, "user_id": user_id})
    if workflow_result.deleted_count == 0:
        raise WorkflowNotFoundError(f"Workflow {workflow_id} was not found")
    await _database().companies.delete_many(query)
    await _database().contacts.delete_many(query)
    await _database().agent_logs.delete_many(query)


async def get_contact(contact_id: str, user_id: str | None = None) -> dict | None:
    query: dict[str, Any] = {"_id": contact_id}
    if user_id is not None:
        query["user_id"] = user_id
    doc = await _database().contacts.find_one(query)
    return _public(doc)


async def record_email_activity(activity: dict) -> str:
    activity_id = activity.get("_id") or f"email_{uuid4().hex}"
    document = {
        **activity,
        "_id": activity_id,
        "sent_at": activity.get("sent_at") or _now(),
    }
    await _database().email_activities.insert_one(document)
    return activity_id


async def get_email_activities(
    workflow_id: str | None = None,
    contact_id: str | None = None,
    user_id: str | None = None,
) -> list[dict]:
    query: dict[str, Any] = {}
    if workflow_id:
        query["workflow_id"] = workflow_id
    if contact_id:
        query["contact_id"] = contact_id
    if user_id:
        query["user_id"] = user_id
    cursor = _database().email_activities.find(query).sort("sent_at", -1)
    return [_public(doc) async for doc in cursor if doc]


async def save_evidence(evidence: dict) -> str:
    evidence_id = evidence.get("_id") or f"ev_{uuid4().hex}"
    document = {
        **evidence,
        "_id": evidence_id,
        "retrieved_at": evidence.get("retrieved_at") or _now(),
    }
    await _database().evidence.insert_one(document)
    return evidence_id


async def get_company_evidence(company_id: str, user_id: str | None = None) -> list[dict]:
    query: dict[str, Any] = {"entity_id": company_id}
    if user_id:
        query["user_id"] = user_id
    cursor = _database().evidence.find(query).sort("retrieved_at", 1)
    return [_public(doc) async for doc in cursor if doc]


async def save_domain_profile(profile: dict) -> str:
    profile_id = profile.get("_id") or profile.get("id") or f"dp_{uuid4().hex}"
    document = {
        **profile,
        "_id": profile_id,
        "id": profile_id,
        "created_at": profile.get("created_at") or _now(),
    }
    await _database().domain_profiles.update_one(
        {"_id": profile_id},
        {"$set": document},
        upsert=True,
    )
    return profile_id


async def get_domain_profile(profile_id: str) -> dict | None:
    doc = await _database().domain_profiles.find_one({"_id": profile_id})
    return _public(doc)


async def list_domain_profiles() -> list[dict]:
    cursor = _database().domain_profiles.find({})
    return [_public(doc) async for doc in cursor if doc]


async def document_stats(user_id: str) -> dict:
    return {
        "workflows": await _database().workflows.count_documents({"user_id": user_id}),
        "companies": await _database().companies.count_documents({"user_id": user_id}),
        "contacts": await _database().contacts.count_documents({"user_id": user_id}),
        "agent_logs": await _database().agent_logs.count_documents({"user_id": user_id}),
        "email_activities": await _database().email_activities.count_documents({"user_id": user_id}),
    }


async def get_analytics_metrics(user_id: str) -> dict[str, Any]:
    from datetime import datetime, timedelta, UTC

    db = _database()
    counts = await document_stats(user_id)

    workflows_cursor = db.workflows.find({"user_id": user_id})
    all_workflows = [_public(doc) async for doc in workflows_cursor if doc]

    total_cost = sum(float(w.get("total_cost_usd", 0.0) or 0.0) for w in all_workflows)
    total_tokens = sum(int(w.get("total_tokens", 0) or 0) for w in all_workflows)
    total_leads = sum(int(w.get("results_count", 0) or 0) for w in all_workflows)
    if total_leads == 0:
        total_leads = counts["contacts"]

    cost_per_lead = round(total_cost / total_leads, 4) if total_leads > 0 else 0.0

    agent_logs_cursor = db.agent_logs.find({"user_id": user_id})
    agent_logs = [_public(doc) async for doc in agent_logs_cursor if doc]

    agent_token_map: dict[str, int] = {}
    agent_cost_map: dict[str, float] = {}
    for log in agent_logs:
        agent = log.get("agent_name") or "other"
        tokens = log.get("tokens", 0) or 0
        cost = log.get("cost_usd", 0.0) or 0.0
        agent_token_map[agent] = agent_token_map.get(agent, 0) + tokens
        agent_cost_map[agent] = round(agent_cost_map.get(agent, 0.0) + cost, 4)

    now = datetime.now(UTC)
    daily_spend = []
    for i in range(6, -1, -1):
        day_date = (now - timedelta(days=i)).date()
        day_label = day_date.strftime("%b %d")
        spend = 0.0
        for w in all_workflows:
            created = w.get("created_at")
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except Exception:
                    created = None
            if created and getattr(created, "date", None) and created.date() == day_date:
                spend += float(w.get("total_cost_usd", 0.0) or 0.0)
        daily_spend.append({"day": day_label, "spend": round(spend, 4)})

    return {
        "total_workflows": counts["workflows"],
        "total_companies": counts["companies"],
        "total_contacts": counts["contacts"],
        "total_emails_sent": counts["email_activities"],
        "total_agent_logs": counts["agent_logs"],
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "total_leads": total_leads,
        "cost_per_lead": cost_per_lead,
        "agent_breakdown": [
            {"name": k, "cost": v, "tokens": agent_token_map.get(k, 0)}
            for k, v in agent_cost_map.items()
        ],
        "daily_spend": daily_spend,
    }

