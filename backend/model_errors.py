"""Actionable failure categories without upstream bodies, keys or user input."""
import asyncio
import httpx
from pydantic import ValidationError
from fastapi import HTTPException

class ModelFailure(ValueError):
    def __init__(self,code,message):self.code=code;self.status_code=502;super().__init__(message)

def failure(error):
    if isinstance(error,ModelFailure):return error.code,str(error)
    if isinstance(error,httpx.HTTPStatusError):
        code=error.response.status_code
        if code in (401,403):return 'provider_authentication','The provider rejected this credential or model permission. Test the saved key in Key vault and confirm model access.'
        if code==429:return 'provider_quota','Provider quota or rate limit reached. Check your provider project billing/quota and retry later.'
        if code==404:return 'provider_model_unavailable','The configured model is unavailable. Choose an available model in Key vault.'
        if code==400:return 'provider_request_rejected','The provider rejected the model request. Check the selected model and its supported response format.'
        return 'provider_unavailable','The model provider is temporarily unavailable. Retry this run later.'
    if isinstance(error,(TimeoutError,httpx.TimeoutException)):return 'model_timeout','The model or workflow exceeded its time budget. Retry or choose a faster available model.'
    if isinstance(error,httpx.TransportError):return 'provider_connection','The provider could not be reached. Check outbound HTTPS connectivity and trusted certificates.'
    if isinstance(error,ValidationError):return 'agent_output_invalid','The agent response did not match its required output contract. No invalid requirement or build was accepted.'
    if isinstance(error,HTTPException):
        if error.status_code in (401,403):return 'policy_denied','Workspace permissions or data policy denied this operation.'
        if error.status_code in (409,503):return 'configuration_unavailable','A credential, route, revision or service is unavailable. Refresh and check Key vault and saved build results.'
    from backend.providers import ProviderNotConfigured
    if isinstance(error,ProviderNotConfigured):return 'model_not_configured','No credential is configured for the selected provider. Save a key and assign a workspace default in Key vault.'
    return 'execution_failed','Node input/output validation or execution failed; inspect configuration and saved build results'
