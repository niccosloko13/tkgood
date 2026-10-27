"""Canonical, read-only Safety contract. Consumes existing detector evidence.

This module cannot navigate, persist/clear incidents or compute intelligence.
Transport-local enforcement and incident persistence remain separate adapters.
"""
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit,parse_qs

CONTRACT=json.loads((Path(__file__).resolve().parents[1]/'config/safety_contract.json').read_text())
VERSION=CONTRACT['version']
FRESH_SECONDS=15


def authenticated_account_evidence(bridge):
    signals=bridge.get('session_signals')
    if signals is not None:
        if hasattr(signals,'model_dump'):signals=signals.model_dump()
        if signals.get('logged_out_cta_present'):return False
        groups=[signals.get('profile_route_present') is True or signals.get('account_avatar_present') is True,
                signals.get('messages_route_present') is True or signals.get('activity_or_inbox_present') is True,
                signals.get('following_authenticated_present') is True]
        return sum(groups)>=2
    return set(bridge.get('session_evidence',[]))=={'visible_own_profile_with_avatar','visible_account_inbox'}


def healthy_route(url):
    try:
        u=urlsplit(url)
        return u.scheme=='https' and u.netloc=='www.tiktok.com' and (u.path=='/' or u.path.rstrip('/')=='/search' and bool(parse_qs(u.query).get('q',[''])[0].strip()))
    except ValueError:return False


@dataclass(frozen=True)
class SafetyDecision:
    page:str
    security:str
    session:str
    may_continue:bool
    reason:str
    transient:bool=False
    version:str=VERSION

    def to_dict(self):return asdict(self)


class SafetyGate:
    VERSION=VERSION
    @staticmethod
    def healthy_route(url):
        return healthy_route(url)

    @staticmethod
    def observation(bridge,*,global_stopped=False,target_blocked=False,pending_targets=False):
        """Normalize existing signals, without claiming fresh/backend admission."""
        page=bridge.get('current_page_status','unknown')
        session=bridge.get('tiktok_session_status','unconfirmed')
        blocker=str(bridge.get('security_stop') or bridge.get('error') or '')
        if bridge.get('challenge') or page in ('challenge','http_403') or re.search(r'403|access.denied|captcha|challenge|verify.*human',blocker,re.I):
            return SafetyDecision('ERROR' if page=='http_403' else 'CHALLENGE','GLOBAL_BLOCKED',session,False,'SECURITY_BLOCK')
        if session in ('login_required','logged_out') or (bridge.get('session_signals') or {}).get('logged_out_cta_present') is True:
            return SafetyDecision('LOGGED_OUT','GLOBAL_BLOCKED',session,False,'LOGGED_OUT')
        state='HEALTHY' if page=='healthy' and bridge.get('page_ready_state')=='complete' else 'LOADING' if bridge.get('page_ready_state') in ('loading','interactive') else 'ERROR' if page=='error' else 'UNKNOWN'
        if global_stopped:return SafetyDecision(state,'GLOBAL_BLOCKED',session,False,'GLOBAL_SECURITY_EVENT')
        if pending_targets:return SafetyDecision(state,'GLOBAL_BLOCKED',session,False,'TARGET_HEALTH_PENDING')
        if target_blocked:return SafetyDecision(state,'TARGET_BLOCKED',session,False,'TARGET_PREVIOUSLY_BLOCKED')
        allowed=state=='HEALTHY' and session=='confirmed'
        return SafetyDecision(state,'OK',session,allowed,'HEALTHY_CONFIRMED' if allowed else 'TRANSIENT_LOADING' if state in ('LOADING','UNKNOWN') else 'SESSION_NOT_STABLE',state in ('LOADING','UNKNOWN'))

    @staticmethod
    def health(bridge,extension_id,build_id):
        """Legacy passive-check evidence shape, with the same admission rules."""
        try:age=(datetime.now(timezone.utc)-datetime.fromisoformat(bridge['last_seen'].replace('Z','+00:00'))).total_seconds()
        except (KeyError,ValueError,TypeError):age=None
        fresh=age is not None and 0<=age<FRESH_SECONDS
        page=bridge.get('current_page_status','unknown');session=bridge.get('tiktok_session_status','unconfirmed')
        evidence={'mode':'SAFE_RECOVERY_CHECK','companion_connected':fresh and bridge.get('extension_id')==extension_id,
            'heartbeat_fresh':fresh,'document_ready':bridge.get('page_ready_state')=='complete',
            'current_url':bridge.get('current_url',''),'tab_id':bridge.get('tab_id'),'page_status':page,
            'challenge_indicators':page=='challenge','http_403_indicators':page=='http_403',
            'account_signals':bridge.get('session_evidence',[]),'session':session,'heartbeat_at':bridge.get('last_seen'),
            'build_matches':bool(build_id) and bridge.get('build_id')==build_id}
        status='BLOCKED' if fresh and page=='http_403' else 'CHALLENGE' if fresh and page=='challenge' else 'UNKNOWN'
        if all((evidence['companion_connected'],evidence['heartbeat_fresh'],evidence['document_ready'],
                evidence['build_matches'],SafetyGate.healthy_route(evidence['current_url']),bridge.get('tab_id') is not None,
                page=='healthy',session=='confirmed',authenticated_account_evidence(bridge))):status='HEALTHY'
        return {'status':status,**evidence}

    @classmethod
    def assess(cls,bridge,extension_id,build_id,**context):
        decision=cls.observation(bridge,**context)
        if decision.may_continue and cls.health(bridge,extension_id,build_id)['status']!='HEALTHY':
            return SafetyDecision('UNKNOWN','OK',decision.session,False,'FRESH_CONFIRMED_HOME_SEARCH_REQUIRED')
        return decision
