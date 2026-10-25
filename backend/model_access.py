"""Request-local model routing: credentials never enter prompts or checkpoints."""
from contextvars import ContextVar
from contextlib import contextmanager
import os

SCOPE = ContextVar('model_scope', default=None)
DATA_SCOPE = ContextVar('model_data_scope', default=None)
VAULT = None
POLICY = None

@contextmanager
def model_data_scope(conversation):
    token = DATA_SCOPE.set(conversation)
    try: yield
    finally: DATA_SCOPE.reset(token)

def enforce_data_policy(mode):
    scope, conversation = SCOPE.get(), DATA_SCOPE.get()
    if POLICY and scope and conversation is not None:
        POLICY.data(scope[0], conversation, effective_mode(mode))

@contextmanager
def model_scope(owner, agent='supervisor'):
    token = SCOPE.set((owner, agent))
    try: yield
    finally: SCOPE.reset(token)

def binding():
    scope = SCOPE.get()
    return VAULT.route(*scope) if VAULT and scope else None

def effective_mode(mode):
    if mode != 'default': return mode
    route = binding()
    if route:return route['provider']
    if VAULT and SCOPE.get():
        from backend.model_errors import ModelFailure
        raise ModelFailure('model_not_configured','Save and verify a Gemini or Groq key in Key vault. All agents use that workspace key automatically.')
    return 'local'

def key_for(mode, config):
    route = binding()
    if route and route['provider'] == mode and route.get('credential_id'):
        return VAULT.reveal_for_service(SCOPE.get()[0], route['credential_id'], mode)
    if VAULT and SCOPE.get():
        credential=VAULT.credential_for(SCOPE.get()[0],mode)
        if credential:return VAULT.reveal_for_service(SCOPE.get()[0],credential,mode)
    return os.getenv(config['key'], '') if config.get('key') else ''

def model_for(mode, config):
    route = binding()
    return route['model'] if route and route['provider'] == mode and route.get('model') else os.getenv(config['model_env'], config['default_model'])
