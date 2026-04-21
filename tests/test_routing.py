"""Unit tests — verify every MCP tool dispatches to the correct Ashby
endpoint and forwards its arguments faithfully.

No network calls are made. `responses` intercepts every outbound HTTP
request. Each test asserts:
  1. the correct URL was hit,
  2. the JSON body matches what the caller passed in (or the expected
     transformation, for the few tools that mutate the payload).
"""

import json

import pytest
import responses

BASE = "https://api.ashbyhq.com"


def _ok(endpoint: str, body: dict | None = None, json_body: dict | None = None):
    """Register a happy-path POST mock and return the RequestsMock call handle."""
    return responses.post(
        f"{BASE}{endpoint}",
        json=json_body or {"success": True, "results": body or {}},
        status=200,
    )


def _sent_body(mock_call) -> dict:
    """Decode the JSON body that was sent to the registered mock."""
    return json.loads(mock_call.calls[0].request.body)


# ---------------------------------------------------------------------------
# Candidate tools
# ---------------------------------------------------------------------------


@responses.activate
async def test_create_candidate_uses_camelcase(call_tool):
    rsp = _ok("/candidate.create")
    args = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "phoneNumber": "555-0100",
        "linkedInUrl": "https://linkedin.com/in/ada",
    }
    await call_tool("create_candidate", args)
    assert _sent_body(rsp) == args


@responses.activate
async def test_search_candidates(call_tool):
    rsp = _ok("/candidate.search")
    await call_tool("search_candidates", {"name": "Ada"})
    assert _sent_body(rsp) == {"name": "Ada"}


@responses.activate
async def test_list_candidates_uses_cursor_pagination(call_tool):
    rsp = _ok("/candidate.list")
    await call_tool("list_candidates", {"limit": 25, "cursor": "abc"})
    assert _sent_body(rsp) == {"limit": 25, "cursor": "abc"}


@responses.activate
async def test_get_candidate(call_tool):
    rsp = _ok("/candidate.info")
    await call_tool("get_candidate", {"id": "cand-123"})
    assert _sent_body(rsp) == {"id": "cand-123"}


@responses.activate
async def test_update_candidate(call_tool):
    rsp = _ok("/candidate.update")
    args = {"candidateId": "cand-123", "email": "new@example.com"}
    await call_tool("update_candidate", args)
    assert _sent_body(rsp) == args


@responses.activate
async def test_add_candidate_tag(call_tool):
    rsp = _ok("/candidate.addTag")
    await call_tool("add_candidate_tag", {"candidateId": "c1", "tagId": "t1"})
    assert _sent_body(rsp) == {"candidateId": "c1", "tagId": "t1"}


@responses.activate
async def test_list_candidate_tags(call_tool):
    rsp = _ok("/candidateTag.list")
    await call_tool("list_candidate_tags", {"includeArchived": True})
    assert _sent_body(rsp) == {"includeArchived": True}


@responses.activate
async def test_add_candidate_to_project(call_tool):
    rsp = _ok("/candidate.addProject")
    await call_tool("add_candidate_to_project", {"candidateId": "c1", "projectId": "p1"})
    assert _sent_body(rsp) == {"candidateId": "c1", "projectId": "p1"}


@responses.activate
async def test_create_candidate_note(call_tool):
    rsp = _ok("/candidate.createNote")
    await call_tool("create_candidate_note", {"candidateId": "c1", "note": "hello"})
    assert _sent_body(rsp) == {"candidateId": "c1", "note": "hello"}


@responses.activate
async def test_list_candidate_notes(call_tool):
    rsp = _ok("/candidate.listNotes")
    await call_tool("list_candidate_notes", {"candidateId": "c1"})
    assert _sent_body(rsp) == {"candidateId": "c1"}


@responses.activate
async def test_list_candidate_client_info(call_tool):
    rsp = _ok("/candidate.listClientInfo")
    await call_tool("list_candidate_client_info", {"candidateId": "c1"})
    assert _sent_body(rsp) == {"candidateId": "c1"}


@responses.activate
async def test_anonymize_candidate(call_tool):
    rsp = _ok("/candidate.anonymize")
    await call_tool("anonymize_candidate", {"candidateId": "c1"})
    assert _sent_body(rsp) == {"candidateId": "c1"}


# ---------------------------------------------------------------------------
# File upload tools — multipart/form-data
# ---------------------------------------------------------------------------


@responses.activate
async def test_upload_candidate_resume(call_tool, tmp_path):
    rsp = _ok("/candidate.uploadResume")
    f = tmp_path / "resume.pdf"
    f.write_bytes(b"%PDF-1.4 dummy")
    await call_tool("upload_candidate_resume", {"candidateId": "c1", "file_path": str(f)})
    req = rsp.calls[0].request
    # Multipart body carries both the candidateId form field and the resume part.
    assert b'name="candidateId"' in req.body
    assert b"c1" in req.body
    assert b'name="resume"' in req.body
    assert b"%PDF-1.4 dummy" in req.body
    # Crucial: no JSON content-type leaked from the default client headers.
    assert req.headers["Content-Type"].startswith("multipart/form-data")


@responses.activate
async def test_upload_candidate_file(call_tool, tmp_path):
    rsp = _ok("/candidate.uploadFile")
    f = tmp_path / "doc.txt"
    f.write_bytes(b"hello")
    await call_tool("upload_candidate_file", {"candidateId": "c1", "file_path": str(f)})
    req = rsp.calls[0].request
    assert b'name="file"' in req.body
    assert b"hello" in req.body


# ---------------------------------------------------------------------------
# Project tools
# ---------------------------------------------------------------------------


@responses.activate
async def test_get_project(call_tool):
    rsp = _ok("/project.info")
    await call_tool("get_project", {"projectId": "p1"})
    assert _sent_body(rsp) == {"projectId": "p1"}


@responses.activate
async def test_list_projects(call_tool):
    rsp = _ok("/project.list")
    await call_tool("list_projects", {"limit": 10})
    assert _sent_body(rsp) == {"limit": 10}


@responses.activate
async def test_search_projects(call_tool):
    rsp = _ok("/project.search")
    await call_tool("search_projects", {"title": "BizOps"})
    assert _sent_body(rsp) == {"title": "BizOps"}


# ---------------------------------------------------------------------------
# Custom field tools
# ---------------------------------------------------------------------------


@responses.activate
async def test_list_custom_fields_strips_client_side_filter(call_tool):
    """objectType is a client-side filter and must NOT be sent to Ashby."""
    rsp = _ok(
        "/customField.list",
        json_body={
            "success": True,
            "results": [
                {"id": "f1", "objectType": "Candidate", "title": "Referred By"},
                {"id": "f2", "objectType": "Application", "title": "Offer Amount"},
                {"id": "f3", "objectType": "Candidate", "title": "Source Detail"},
            ],
        },
    )
    result = await call_tool("list_custom_fields", {"objectType": "Candidate", "limit": 100})
    # objectType is applied locally
    assert "objectType" not in _sent_body(rsp)
    assert _sent_body(rsp) == {"limit": 100}
    # The response is filtered to just Candidate fields.
    assert [r["id"] for r in result["results"]] == ["f1", "f3"]


@responses.activate
async def test_list_custom_fields_no_filter_passes_all(call_tool):
    rsp = _ok(
        "/customField.list",
        json_body={
            "success": True,
            "results": [
                {"id": "f1", "objectType": "Candidate"},
                {"id": "f2", "objectType": "Job"},
            ],
        },
    )
    result = await call_tool("list_custom_fields", {})
    assert _sent_body(rsp) == {}
    assert len(result["results"]) == 2


@responses.activate
async def test_get_custom_field(call_tool):
    rsp = _ok("/customField.info")
    await call_tool("get_custom_field", {"customFieldId": "cf-1"})
    assert _sent_body(rsp) == {"customFieldId": "cf-1"}


@responses.activate
async def test_create_custom_field(call_tool):
    rsp = _ok("/customField.create")
    args = {"title": "Referral Source", "fieldType": "String", "objectType": "Candidate"}
    await call_tool("create_custom_field", args)
    assert _sent_body(rsp) == args


@responses.activate
async def test_set_custom_field_value_string(call_tool):
    rsp = _ok("/customField.setValue")
    args = {"objectId": "c1", "objectType": "Candidate", "fieldId": "f1", "fieldValue": "Alice"}
    await call_tool("set_custom_field_value", args)
    assert _sent_body(rsp) == args


@responses.activate
async def test_set_custom_field_value_number_range(call_tool):
    rsp = _ok("/customField.setValue")
    args = {
        "objectId": "j1",
        "objectType": "Job",
        "fieldId": "f-salary",
        "fieldValue": {"type": "number-range", "minValue": 100000, "maxValue": 150000},
    }
    await call_tool("set_custom_field_value", args)
    assert _sent_body(rsp) == args


# ---------------------------------------------------------------------------
# Job tools
# ---------------------------------------------------------------------------


@responses.activate
async def test_create_job_uses_camelcase(call_tool):
    rsp = _ok("/job.create")
    args = {"title": "SWE", "teamId": "t1", "locationId": "l1"}
    await call_tool("create_job", args)
    assert _sent_body(rsp) == args


@responses.activate
async def test_search_jobs(call_tool):
    rsp = _ok("/job.search")
    await call_tool("search_jobs", {"title": "Engineer"})
    assert _sent_body(rsp) == {"title": "Engineer"}


@responses.activate
async def test_list_jobs_defaults_status_to_open(call_tool):
    """The handler injects status=['Open'] when the caller omits it."""
    rsp = _ok("/job.list")
    await call_tool("list_jobs", {})
    assert _sent_body(rsp) == {"status": ["Open"]}


@responses.activate
async def test_list_jobs_respects_explicit_status(call_tool):
    rsp = _ok("/job.list")
    await call_tool("list_jobs", {"status": ["Closed", "Archived"]})
    assert _sent_body(rsp) == {"status": ["Closed", "Archived"]}


@responses.activate
async def test_get_job(call_tool):
    rsp = _ok("/job.info")
    await call_tool("get_job", {"id": "j1"})
    assert _sent_body(rsp) == {"id": "j1"}


@responses.activate
async def test_update_job(call_tool):
    rsp = _ok("/job.update")
    await call_tool("update_job", {"jobId": "j1", "title": "New title"})
    assert _sent_body(rsp) == {"jobId": "j1", "title": "New title"}


@responses.activate
async def test_set_job_status(call_tool):
    rsp = _ok("/job.setStatus")
    await call_tool("set_job_status", {"jobId": "j1", "status": "Closed"})
    assert _sent_body(rsp) == {"jobId": "j1", "status": "Closed"}


# ---------------------------------------------------------------------------
# Application tools
# ---------------------------------------------------------------------------


@responses.activate
async def test_create_application_uses_camelcase(call_tool):
    rsp = _ok("/application.create")
    args = {"candidateId": "c1", "jobId": "j1", "sourceId": "s1"}
    await call_tool("create_application", args)
    assert _sent_body(rsp) == args


@responses.activate
async def test_list_applications_cursor_pagination(call_tool):
    rsp = _ok("/application.list")
    await call_tool("list_applications", {"status": "Active", "limit": 50})
    assert _sent_body(rsp) == {"status": "Active", "limit": 50}


@responses.activate
async def test_get_application(call_tool):
    rsp = _ok("/application.info")
    await call_tool("get_application", {"applicationId": "a1", "expand": ["openings"]})
    assert _sent_body(rsp) == {"applicationId": "a1", "expand": ["openings"]}


@responses.activate
async def test_update_application(call_tool):
    rsp = _ok("/application.update")
    await call_tool("update_application", {"applicationId": "a1", "sourceId": "s2"})
    assert _sent_body(rsp) == {"applicationId": "a1", "sourceId": "s2"}


@responses.activate
async def test_change_application_stage(call_tool):
    rsp = _ok("/application.change_stage")
    await call_tool("change_application_stage", {"applicationId": "a1", "interviewStageId": "st1"})
    assert _sent_body(rsp) == {"applicationId": "a1", "interviewStageId": "st1"}


@responses.activate
async def test_change_application_source(call_tool):
    rsp = _ok("/application.change_source")
    await call_tool("change_application_source", {"applicationId": "a1", "sourceId": "s1"})
    assert _sent_body(rsp) == {"applicationId": "a1", "sourceId": "s1"}


@responses.activate
async def test_transfer_application(call_tool):
    rsp = _ok("/application.transfer")
    await call_tool("transfer_application", {"applicationId": "a1", "jobId": "j2"})
    assert _sent_body(rsp) == {"applicationId": "a1", "jobId": "j2"}


@responses.activate
async def test_add_application_hiring_team_member(call_tool):
    rsp = _ok("/application.addHiringTeamMember")
    args = {"applicationId": "a1", "teamMemberId": "u1", "roleId": "r1"}
    await call_tool("add_application_hiring_team_member", args)
    assert _sent_body(rsp) == args


@responses.activate
async def test_remove_application_hiring_team_member(call_tool):
    rsp = _ok("/application.removeHiringTeamMember")
    args = {"applicationId": "a1", "teamMemberId": "u1", "roleId": "r1"}
    await call_tool("remove_application_hiring_team_member", args)
    assert _sent_body(rsp) == args


# ---------------------------------------------------------------------------
# Interview tools
# ---------------------------------------------------------------------------


@responses.activate
async def test_get_interview(call_tool):
    rsp = _ok("/interview.info")
    await call_tool("get_interview", {"id": "iv1"})
    assert _sent_body(rsp) == {"id": "iv1"}


@responses.activate
async def test_list_interviews(call_tool):
    rsp = _ok("/interview.list")
    await call_tool("list_interviews", {"includeArchived": False})
    assert _sent_body(rsp) == {"includeArchived": False}


@responses.activate
async def test_create_interview_schedule(call_tool):
    rsp = _ok("/interviewSchedule.create")
    args = {
        "applicationId": "a1",
        "interviewEvents": [
            {
                "startTime": "2026-05-01T15:00:00.000Z",
                "endTime": "2026-05-01T16:00:00.000Z",
                "interviewers": [{"email": "bob@example.com"}],
            }
        ],
    }
    await call_tool("create_interview_schedule", args)
    assert _sent_body(rsp) == args


@responses.activate
async def test_list_interview_schedules(call_tool):
    rsp = _ok("/interviewSchedule.list")
    await call_tool("list_interview_schedules", {"applicationId": "a1"})
    assert _sent_body(rsp) == {"applicationId": "a1"}


@responses.activate
async def test_update_interview_schedule(call_tool):
    rsp = _ok("/interviewSchedule.update")
    args = {
        "interviewScheduleId": "sch-1",
        "interviewEvent": {
            "interviewEventId": "ev-1",
            "startTime": "2026-05-01T17:00:00.000Z",
            "endTime": "2026-05-01T18:00:00.000Z",
            "interviewers": [{"email": "bob@example.com"}],
        },
    }
    await call_tool("update_interview_schedule", args)
    assert _sent_body(rsp) == args


@responses.activate
async def test_cancel_interview_schedule(call_tool):
    rsp = _ok("/interviewSchedule.cancel")
    await call_tool("cancel_interview_schedule", {"id": "sch-1", "allowReschedule": True})
    assert _sent_body(rsp) == {"id": "sch-1", "allowReschedule": True}


@responses.activate
async def test_list_interview_events(call_tool):
    rsp = _ok("/interviewEvent.list")
    await call_tool("list_interview_events", {"interviewScheduleId": "sch-1", "expand": ["interview"]})
    assert _sent_body(rsp) == {"interviewScheduleId": "sch-1", "expand": ["interview"]}


@responses.activate
async def test_list_interview_plans(call_tool):
    rsp = _ok("/interviewPlan.list")
    await call_tool("list_interview_plans", {"includeArchived": True})
    assert _sent_body(rsp) == {"includeArchived": True}


@responses.activate
async def test_list_interview_stages(call_tool):
    rsp = _ok("/interviewStage.list")
    await call_tool("list_interview_stages", {"interviewPlanId": "plan-1"})
    assert _sent_body(rsp) == {"interviewPlanId": "plan-1"}


@responses.activate
async def test_get_interview_stage(call_tool):
    rsp = _ok("/interviewStage.info")
    await call_tool("get_interview_stage", {"interviewStageId": "st-1"})
    assert _sent_body(rsp) == {"interviewStageId": "st-1"}


@responses.activate
async def test_list_interview_stage_groups(call_tool):
    rsp = _ok("/interviewStageGroup.list")
    await call_tool("list_interview_stage_groups", {"interviewPlanId": "plan-1"})
    assert _sent_body(rsp) == {"interviewPlanId": "plan-1"}


# ---------------------------------------------------------------------------
# Behaviour — error paths and auth
# ---------------------------------------------------------------------------


@responses.activate
async def test_auth_uses_http_basic(call_tool, ashby_client):
    """Every request must carry HTTP Basic auth built from the loaded
    API key — regardless of what value that key actually has, the
    shape must be `Basic base64(api_key:)`."""
    import base64

    rsp = _ok("/candidate.search")
    await call_tool("search_candidates", {"name": "x"})
    sent_auth = rsp.calls[0].request.headers["Authorization"]
    expected = "Basic " + base64.b64encode(f"{ashby_client.api_key}:".encode()).decode()
    assert sent_auth == expected


@responses.activate
async def test_error_response_surfaced_to_caller(call_tool):
    """Ashby's own error envelopes should flow through verbatim."""
    responses.post(
        f"{BASE}/candidate.search",
        json={"success": False, "errors": ["invalid_input"]},
        status=200,
    )
    result = await call_tool("search_candidates", {"name": ""})
    assert result == {"success": False, "errors": ["invalid_input"]}


async def test_unknown_tool_returns_error_text(call_tool):
    """Dispatcher catches unknown names and returns an error string,
    not a crash."""
    result = await call_tool("definitely_not_a_tool", {})
    assert isinstance(result, str)
    assert "Unknown tool" in result
