"""
tests/test_chatbot.py
======================
Tests for the offline rule-based chatbot.
"""
import pytest
from fastapi.testclient import TestClient


def test_chatbot_greeting(auth_client: TestClient):
    """Chatbot responds to a greeting."""
    response = auth_client.post(
        "/api/chatbot/message",
        json={"message": "hello"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert len(data["response"]) > 10


def test_chatbot_ipec_intent(auth_client: TestClient):
    """Chatbot recognises the IPEC intent and returns regulatory info."""
    response = auth_client.post(
        "/api/chatbot/message",
        json={"message": "What is IPEC?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "IPEC" in data["response"]


def test_chatbot_csp_intent(auth_client: TestClient):
    """Chatbot recognises the CSP/WCS intent."""
    response = auth_client.post(
        "/api/chatbot/message",
        json={"message": "Tell me about the WCS score"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "WCS" in data["response"] or "Weighted" in data["response"]


def test_chatbot_fallback(auth_client: TestClient):
    """Chatbot returns a helpful fallback for unknown queries."""
    response = auth_client.post(
        "/api/chatbot/message",
        json={"message": "xyzzy completely unknown query 99999"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["response"]) > 20


def test_chatbot_requires_auth(client: TestClient):
    """Chatbot endpoint requires authentication."""
    response = client.post(
        "/api/chatbot/message",
        json={"message": "hello"},
    )
    assert response.status_code == 401


def test_chatbot_help_intent(auth_client: TestClient):
    """Chatbot responds to help request."""
    response = auth_client.post(
        "/api/chatbot/message",
        json={"message": "help"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["response"]) > 50
