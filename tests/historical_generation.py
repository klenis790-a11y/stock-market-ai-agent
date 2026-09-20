"""Test-only v1 request harnesses. Never imported by production.
Historical response matrices exercise retained public validators; active v2 wiring
is tested independently in test_v2_activation.py.
"""
import json
import logging
from datetime import datetime, timezone
from src import technical_analyst as ta, horizon_synthesis as hs
from src.generation_contracts import TECHNICAL_V1, HORIZON_V1

def analyze_technical_snapshot(snapshot, catalog, horizon):
    _preflight, _parse = ta._preflight, ta._parse
    openai_client, INSTRUCTIONS, SCHEMA = ta.openai_client, ta.INSTRUCTIONS, ta.SCHEMA
    TechnicalValidationError = ta.TechnicalValidationError
    def TechnicalSignal(*args):
        return ta.TechnicalSignal(*args, analyst_methodology_version=TECHNICAL_V1)
    items, available = _preflight(snapshot,catalog,horizon)
    response = openai_client.request_text(input=json.dumps({'horizon':horizon,
        'technical_evidence':catalog.to_packet()},allow_nan=False), instructions=INSTRUCTIONS,
        max_output_tokens=5000,text={'format':{'type':'json_schema','name':'technical_analysis',
                                            'strict':True,'schema':SCHEMA}})
    try:
        data = json.loads(response)
    except (TypeError,ValueError):
        raise TechnicalValidationError('TECHNICAL_ANALYST_INVALID_JSON') from None
    analysis = _parse(data,items,available)
    return TechnicalSignal(catalog.provenance,horizon,analysis,catalog.methodology_version,openai_client.MODEL)

def synthesize_horizon(context):
    require_synthesis_ready = hs.require_synthesis_ready
    _packet, _schema, canonical_json = hs._packet, hs._schema, hs.canonical_json
    openai_client, INSTRUCTIONS, _validate = hs.openai_client, hs.INSTRUCTIONS, hs._validate
    HorizonSynthesisError, utc_timestamp = hs.HorizonSynthesisError, hs.utc_timestamp
    def IntegratedResearchView(*args):
        return hs.IntegratedResearchView(*args, methodology_version=HORIZON_V1)
    validated = require_synthesis_ready(context)  # Mandatory, before packet construction or IO.
    try:
        substage = 'PACKET_CONSTRUCTION'
        try:
            packet = _packet(validated)
            substage = 'INPUT_SERIALIZATION'
            serialized = canonical_json(packet)
            substage = 'SCHEMA_CONSTRUCTION'
            schema = _schema(packet)
        except Exception as error:
            kind = error.synthesis_failure_type if isinstance(error, HorizonSynthesisError) else 'PRE_REQUEST'
            safe_type = type(error).__name__ if type(error) in (ValueError, TypeError, KeyError, AttributeError, IndexError, RuntimeError) else 'Exception'
            raise HorizonSynthesisError(kind, substage=substage, error_type=safe_type) from None
        try:
            response = openai_client.request_text(input=serialized, instructions=INSTRUCTIONS,
                max_output_tokens=5000, require_completed=True,
                text={'format':{'type':'json_schema','name':'horizon_synthesis','strict':True,'schema':schema}})
        except RuntimeError as error:
            kind = getattr(error,'synthesis_failure_type','API_REQUEST')
            raise HorizonSynthesisError('RESPONSE_EXTRACTION' if kind == 'RESPONSE_EXTRACTION' else 'API_REQUEST',
                response_detail=getattr(error, 'synthesis_response_detail', None)) from None
        if not isinstance(response,str) or not response.strip():
            raise HorizonSynthesisError('RESPONSE_EXTRACTION')
        try:
            data = json.loads(response)
        except (ValueError,TypeError):
            raise HorizonSynthesisError('INVALID_JSON') from None
        output = _validate(data,packet)
        return IntegratedResearchView(validated,output,utc_timestamp(datetime.now(timezone.utc).isoformat()),openai_client.MODEL)
    except HorizonSynthesisError as error:
        logging.getLogger(__name__).error('stage=SYNTHESIS operation=horizon_synthesis failure_type=%s substage=%s error_type=%s detail=withheld',error.synthesis_failure_type,error.substage,error.error_type)
        raise
