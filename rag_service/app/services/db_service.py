"""Database helpers for lightweight agent state logging."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, Optional

import psycopg2

from app.config import settings

logger = logging.getLogger(__name__)


def _normalize_workflow_id(workflow_id: str) -> Optional[str]:
	if not workflow_id:
		return None
	try:
		return str(uuid.UUID(str(workflow_id)))
	except (ValueError, TypeError):
		return None


def _log_agent_state_sync(
	*,
	workflow_id: str,
	agent_name: str,
	state_data: Dict[str, Any],
	parent_agent: Optional[str] = None,
	next_agent: Optional[str] = None,
	handoff_data: Optional[Dict[str, Any]] = None,
) -> None:
	wf_id = _normalize_workflow_id(workflow_id)
	if wf_id is None:
		return

	conn = None
	cur = None
	try:
		try:
			conn = psycopg2.connect(settings.DATABASE_URL)
		except Exception:
			db_host = os.environ.get("DB_HOST", "postgres")
			db_port = os.environ.get("DB_PORT", "5432")
			db_name = os.environ.get("DB_NAME", "ai_ba_db")
			db_user = os.environ.get("DB_USER", "postgres")
			db_password = os.environ.get("DB_PASSWORD", "postgres")
			fallback_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
			conn = psycopg2.connect(fallback_url)
		cur = conn.cursor()

		cur.execute(
			"""
			INSERT INTO agent_state
				(workflow_id, agent_name, state_data, parent_agent, next_agent, handoff_data)
			VALUES
				(%s::uuid, %s, %s::jsonb, %s, %s, %s::jsonb)
			""",
			(
				wf_id,
				agent_name,
				json.dumps(state_data or {}),
				parent_agent,
				next_agent,
				json.dumps(handoff_data or {}),
			),
		)
		conn.commit()
	except Exception as exc:
		logger.warning("log_agent_state_failed: %s", exc)
	finally:
		if cur is not None:
			cur.close()
		if conn is not None:
			conn.close()


async def log_agent_state(
	*,
	workflow_id: str,
	agent_name: str,
	state_data: Dict[str, Any],
	parent_agent: Optional[str] = None,
	next_agent: Optional[str] = None,
	handoff_data: Optional[Dict[str, Any]] = None,
) -> None:
	await asyncio.to_thread(
		_log_agent_state_sync,
		workflow_id=workflow_id,
		agent_name=agent_name,
		state_data=state_data,
		parent_agent=parent_agent,
		next_agent=next_agent,
		handoff_data=handoff_data,
	)


