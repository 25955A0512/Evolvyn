"""Normalize provider-returned Instagram identifiers without conflating their namespaces."""
import json,re

def identifiers(profile):
    if not isinstance(profile,dict):raise ValueError('Invalid Instagram profile')
    result={}
    for field in ('id','user_id'):
        if field not in profile:continue
        value=profile[field]
        if type(value) not in (str,int) or not re.fullmatch(r'\d{1,100}',str(value)):raise ValueError('Invalid Instagram identifier')
        result[field]=str(value)
    if not result:raise ValueError('Instagram identifier missing')
    return result

def account_id(identity):return identity.get('user_id') or identity['id']

def verify_authorized_profile(profile,subject,token):
    identity=identifiers(profile)
    if subject not in identity.values():raise ValueError('Instagram authorized subject mismatch')
    username=profile.get('username')
    if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z0-9._]{1,30}',username):raise ValueError('Invalid Instagram username')
    if token and token in json.dumps(profile):raise ValueError('Credential reflection')
    return account_id(identity),identity

def verify_bound_profile(profile,bound_id,expected=None):
    identity=identifiers(profile)
    if account_id(identity)!=bound_id:raise ValueError('Instagram account changed')
    if expected and any(identity.get(field)!=value for field,value in expected.items()):raise ValueError('Instagram identity mapping changed')
    return identity
