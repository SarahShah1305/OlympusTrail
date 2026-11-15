"""Offline coverage for co-mounted guide calls and the explicit HTTP fallback."""
import asyncio
from types import SimpleNamespace
import httpx
import pytest
from fastapi import HTTPException
from ai_guide import planner_client as client

@pytest.fixture(autouse=True)
def real_mode(monkeypatch):
    monkeypatch.setenv('USE_MOCK', '0')
    monkeypatch.delenv('PLANNER_MODE', raising=False)

PAYLOAD = dict(start=dict(row=1,col=1),goal_type='ice')

def test_inprocess_success_never_opens_http(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('In-process calls must not open an HTTP client')
    monkeypatch.setattr(httpx, 'AsyncClient', blocked)
    app=SimpleNamespace(state=SimpleNamespace(calculate=lambda request: dict(status='ok', request=request.model_dump())))
    with client.inprocess_planner(app):
        result=asyncio.run(client.call_planner(PAYLOAD))
    assert result['status']=='ok' and result['_mock'] is False

@pytest.mark.parametrize('status,detail,expected',[(422,'rejected','start position'),(422,client._BLOCKED_START,'excluded by your filters'),(503,'missing','terrain data'),(500,'secret','HTTP 500')])
def test_inprocess_errors_match_http(status,detail,expected):
    def reject(request): raise HTTPException(status_code=status,detail=detail)
    app=SimpleNamespace(state=SimpleNamespace(calculate=reject))
    with client.inprocess_planner(app), pytest.raises(client.PlannerError,match=expected):
        asyncio.run(client.call_planner(PAYLOAD))

def test_http_transport_and_production_url(monkeypatch):
    monkeypatch.setenv('PLANNER_MODE','http')
    monkeypatch.delenv('PLANNER_URL',raising=False)
    monkeypatch.setenv('VERCEL_PROJECT_PRODUCTION_URL','production.example')
    monkeypatch.setenv('VERCEL_URL','protected.example')
    original=httpx.AsyncClient
    def handle(request):
        assert str(request.url)=='https://production.example/route'
        return httpx.Response(200,json={'status':'ok'})
    def factory(**kwargs):
        assert kwargs['timeout']==30.0
        return original(**kwargs,transport=httpx.MockTransport(handle))
    monkeypatch.setattr(httpx,'AsyncClient',factory)
    assert asyncio.run(client.call_planner(PAYLOAD)) == {'status':'ok','_mock':False}

def test_explicit_http_overrides_single_app(monkeypatch):
    monkeypatch.setenv('PLANNER_MODE','http')
    with client.inprocess_planner(object()): assert client._inprocess_app() is None
