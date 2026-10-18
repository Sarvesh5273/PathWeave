"""Source-first Search/Fetch/Agent, followed by paced Groq extraction and preference fit.

Early listings remain visible; an individual failed extraction never removes a lead.
The same public source observations later feed the FalkorDB preparation bridge.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import re
import time

from .ai import AIError,ai_warning_is_fatal
from .basic import BasicDiscoveryEngine
from .bridge import review_listing_requirements
from .contracts import DiscoveryListing,DiscoveryPreferences,EngineResult,ExtractionResult,RunEvent
from .extract import ListingExtractor,selected_metadata
from .filters import classify_constraints,source_filter_evidence
from .preferences import evidence_status,score_preferences
from .ranking import role_relevance
from .urls import canonical_url
from app.models import utc_now


def fit_rows(rows,batch):
    if not isinstance(rows,list) or len(rows)!=len(batch) or not all(isinstance(r,dict) for r in rows):return None
    ids=[r.get('id') for r in rows]
    if not all(isinstance(i,str) for i in ids) or len(set(ids))!=len(ids) or set(ids)!={v.id for v in batch}:return None
    for row in rows:
        score,parts,reasons=row.get('score'),row.get('score_breakdown'),row.get('reasons')
        if type(score)is not int or not 0<=score<=100 or not isinstance(parts,dict) or not parts:return None
        caps={'role':70,'keywords':20,'organization':10}
        if any(k not in caps or type(v)is not int or not 0<=v<=caps[k] for k,v in parts.items()):return None
        if not isinstance(reasons,list) or any(not isinstance(r,str) for r in reasons):return None
    mapped={row['id']:row for row in rows}
    return [v.model_copy(update={k:mapped[v.id][k] for k in ('score','score_breakdown','reasons')}) for v in batch]


class DiscoveryEngine:
    def __init__(self,settings,ledger,*,web=None,browser=None,extractor=None,scorer=None):
        self.settings=settings;self.ledger=ledger
        self.finder=BasicDiscoveryEngine(settings,ledger,web=web,browser=browser,follow_agent_links=True)
        self.extractor=extractor or ListingExtractor(settings)
        self.scorer=scorer or score_preferences

    def run(self,preferences: DiscoveryPreferences,*,previous=None,previous_pages=None,on_event=None,on_progress=None,
            max_enrichments=None):
        result=EngineResult()
        def event(stage,message,url=''):
            item=RunEvent(stage=stage,message=message,url=url,timestamp=utc_now())
            result.events.append(item)
            if on_event:on_event(item)
        def publish():
            if on_progress:on_progress(result.model_copy(deep=True))
        def early(found):
            # Early score is explicit rule relevance. No background inference is
            # claimed before the actual model stage occurs.
            initial=[]
            for start in range(0,len(found.listings),20):
                values,_=score_preferences(found.listings[start:start+20],preferences)
                initial.extend(values)
            result.listings=[evidence_status(v) for v in initial]
            result.pages=found.pages
            publish()
        def finding_event(item):
            if item.stage=='done' or item.stage=='extract' and 'deferred' in item.message:
                return
            if item.stage=='plan':item=item.model_copy(update={'message':'Rule-built Search, batched Fetch and named-company Agent. Candidates appear before Groq requirements review.'})
            if on_event:on_event(item)
        found=self.finder.run(preferences,previous=previous,previous_pages=previous_pages,on_event=finding_event,on_progress=early)
        result=found
        result.events=[e for e in result.events if not (e.stage=='extract' and 'deferred' in e.message) and e.stage!='done']
        for e in result.events:
            if e.stage=='plan':e.message='Rule-built Search, batched Fetch and named-company Agent. Candidates appear before Groq requirements review.'
        # Do not emit a second duplicated model/read stage. Final usage/events
        # clearly identify what was actually attempted.
        result.usage.update({'ai_attempts':0,'extractions':0,'extraction_attempts':0,'extraction_cached':0,'match_calls':0})
        deadline=time.monotonic()+min(240,max(0,self.settings.discovery_enrichment_seconds))
        maximum=min(36,max(0,self.settings.discovery_enrichment_pages if max_enrichments is None else max_enrichments))
        by_id={v.id:v for v in result.listings}
        choices={}
        for listing in result.listings:
            pages=[p for p in result.pages if canonical_url(listing.source_url) in {canonical_url(p.snapshot.url),canonical_url(p.requested_url)}]
            norm=lambda value:' '.join(re.sub(r'[\u2010-\u2015]','-',value).split()).casefold()
            page=max(pages,key=lambda p:(norm(p.snapshot.title).startswith(norm(listing.title)),p.snapshot.checked_at)) if pages else None
            if page and listing.verification!='uncertain' and listing.call_status!='closed':choices[listing.id]=page
        def priority(listing):
            return (listing.constraint_status=='excluded',not any(preferences.companies and c.casefold() in listing.organization.casefold() for c in preferences.companies),
                    listing.constraint_status!='match',-role_relevance(preferences,listing.title,listing.summary))
        ordered=sorted(result.listings,key=priority)
        fatal=False
        def admit(stage):
            if time.monotonic()>=deadline:raise AIError('Discovery enrichment time budget reached.',code='deadline')
            if not self.ledger.reserve('ai_calls',1,self.settings.discovery_daily_ai_calls):
                raise AIError('Daily Groq allowance reached; retrieved candidates remain visible.',code='budget')
            result.usage['ai_attempts']+=1
            result.usage[stage]+=1
        event('extract','Retrieved candidates are visible. Reading supported requirements with Groq before target selection.')
        # Preserve at least one bounded scoring window; both stages share provider
        # admission and the same configured model/output quotas.
        scoring_reserve=min(65,max(10,self.settings.discovery_ai_max_wait_seconds))
        for listing in ordered:
            page=choices.get(listing.id)
            if page is None:continue
            if listing.requirements:
                listing=review_listing_requirements(listing,page)
                by_id[listing.id]=evidence_status(classify_constraints(source_filter_evidence(selected_metadata(listing),page),preferences));continue
            key='progressive-extract-v2:'+hashlib.sha256((page.snapshot.url+'|'+page.snapshot.content_hash+'|'+listing.title+'|'+listing.cycle+'|'+self.settings.groq_model).encode()).hexdigest()
            cached=self.ledger.cached(key)
            if cached is not None:
                try:
                    extracted=ExtractionResult.model_validate(cached)
                    value=extracted.listings[0] if len(extracted.listings)==1 else None
                    if not value or (value.id,value.title,value.cycle)!=(listing.id,listing.title,listing.cycle):raise ValueError('Mismatched cache')
                    value=review_listing_requirements(value,page)
                    if value.enrichment_status!='complete':raise ValueError('Incomplete cache')
                    extracted.listings=[value]
                except (ValueError,TypeError):
                    cached=None;self.ledger.delete_cache(key)
                else:
                    result.usage['extraction_cached']+=1
                    event('extract','Reused source-validated requirements from identical content.',page.snapshot.url)
            if cached is None and (fatal or not self.settings.groq_key or result.usage['extraction_attempts']>=maximum or time.monotonic()+scoring_reserve>=deadline):
                listing.enrichment_status='pending';by_id[listing.id]=evidence_status(listing)
                continue
            if cached is None:
                result.usage['extraction_attempts']+=1
                # Smaller output reservations permit another call or scoring
                # within Groq's output-per-minute budget without disabling AI.
                config=replace(self.settings,discovery_ai_max_output_tokens=min(900,self.settings.discovery_ai_max_output_tokens))
                extractor=self.extractor if not isinstance(self.extractor,ListingExtractor) else ListingExtractor(config,self.extractor.transport)
                try:
                    extracted=extractor.extract_selected(page,listing,preferences,
                        remaining_seconds=max(0,deadline-time.monotonic()-scoring_reserve),on_call=lambda:admit('extractions'))
                except (AIError,ValueError) as exc:extracted=ExtractionResult(warnings=[str(exc)])
                event('extract',f'Groq requirements: {len(extracted.listings)} supported posting result(s).',page.snapshot.url)
            for warning in extracted.warnings:
                result.errors.append(warning);result.partial=True;event('warning',warning,page.snapshot.url)
            fatal=fatal or any(ai_warning_is_fatal(w) for w in extracted.warnings)
            details=next((v for v in extracted.listings if v.id==listing.id),None)
            if details:
                # Source URL/title/cycle/selection identity do not come from the model.
                details=listing.model_copy(update={'requirements':details.requirements,
                    'enrichment_status':details.enrichment_status})
                details.id=listing.id;details.apply_url=listing.apply_url;details.title=listing.title
                details.cycle=listing.cycle;details.saved=listing.saved;details.hidden=listing.hidden
                details.source_url=page.snapshot.url;details.checked_at=page.snapshot.checked_at;details.found_via=listing.found_via
                details=review_listing_requirements(details,page)
                details=source_filter_evidence(selected_metadata(details),page)
                by_id[listing.id]=evidence_status(classify_constraints(details,preferences))
                if details.enrichment_status=='complete':
                    self.ledger.cache(key,extracted.model_copy(update={'listings':[details]}).model_dump(mode='json'),86400)
            else:
                listing.enrichment_status='failed'
                by_id[listing.id]=evidence_status(listing)
            result.listings=[by_id[v.id] for v in result.listings];publish()
        # All retrieved candidates remain, including failures and unknown benefits.
        event('match','Scoring search preferences with Groq. Must-haves and knowledge readiness are separate.')
        scored=[]
        candidates=sorted(by_id.values(),key=priority)
        for offset in range(0,len(candidates),20):
            batch=candidates[offset:offset+20]
            scoring_config=None if fatal or time.monotonic()>=deadline else self.settings
            key='progressive-fit-v2:'+hashlib.sha256((preferences.model_dump_json()+'|'+self.settings.groq_model+'|'+json.dumps([
                [v.id,v.title,v.organization,v.summary,[f.model_dump(mode='json') for f in v.requirements]] for v in batch],ensure_ascii=False)).encode()).hexdigest()
            cached=self.ledger.cached(key)
            fitted=fit_rows(cached,batch)
            if fitted is not None:
                fitted=[v.model_copy(update={'score_mode':'cached'}) for v in fitted]
                warnings=[]
            else:
                try:
                    proposed,warnings=self.scorer(batch,preferences,scoring_config,
                        remaining_seconds=max(1,deadline-time.monotonic()),on_call=lambda:admit('match_calls'))
                    fitted=fit_rows([v.model_dump(mode='json') for v in proposed],batch)
                    if fitted is not None:
                        modes={v.id:v.score_mode for v in proposed}
                        fitted=[v.model_copy(update={'score_mode':modes[v.id]}) for v in fitted]
                except (AIError,ValueError,TypeError) as exc:
                    warnings=[str(exc)]
                if fitted is None:
                    warnings.append('Preference scorer returned invalid/incomplete IDs; all candidates retained with rule scores.')
                    fitted,_=score_preferences(batch,preferences)
                if fitted and all(v.score_mode=='groq' for v in fitted):
                    self.ledger.cache(key,[{'id':v.id,'score':v.score,'score_breakdown':v.score_breakdown,'reasons':v.reasons} for v in fitted],86400)
            for warning in warnings:
                result.errors.append(warning);result.partial=True;event('warning',warning)
            scored.extend(evidence_status(classify_constraints(v,preferences)) for v in fitted)
            result.listings=scored+candidates[offset+len(batch):]
            publish()
        result.listings=sorted(scored,key=lambda v:(v.constraint_status!='match',v.constraint_status=='excluded',-v.score))
        pending=sum(v.enrichment_status in {'pending','failed','partial'} for v in result.listings)
        if pending:
            result.partial=True
            event('coverage',f'{pending} retrieved candidates have pending/partial requirements; select a target to inspect or retry just that source.')
        result.errors=list(dict.fromkeys(result.errors))
        event('done',f'Discovery finished: {len(result.listings)} candidates retained; {sum(v.constraint_status=="match" for v in result.listings)} satisfy selected source-supported filters.')
        publish()
        return result
