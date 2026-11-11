# -*- coding: utf-8 -*-
"""Dependency-free helpers for this skill's explicitly limited JSON Schema subset."""
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def read_json(path):
    def invalid(value):
        raise ValueError('Non-finite JSON number: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=invalid)

def write_json(path, value):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def schema_errors(value, schema, root=None, path='$'):
    """Checks only the keywords used in the bundled schemas, not arbitrary schemas."""
    root = root or schema
    if '$ref' in schema:
        return schema_errors(value, root['$defs'][schema['$ref'].split('/')[-1]], root, path)
    errors = []
    kinds = schema.get('type', [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    checks = {'object':lambda x:isinstance(x,dict), 'array':lambda x:isinstance(x,list),
              'string':lambda x:isinstance(x,str), 'boolean':lambda x:isinstance(x,bool),
              'integer':lambda x:isinstance(x,int) and not isinstance(x,bool),
              'number':lambda x:isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x),
              'null':lambda x:x is None}
    if kinds and not any(checks[k](value) for k in kinds):
        return [f'{path}: expected {kinds}']
    if 'enum' in schema and value not in schema['enum']:
        errors.append(f'{path}: must be one of {schema["enum"]}')
    if isinstance(value,dict):
        props = schema.get('properties',{})
        for k in schema.get('required',[]):
            if k not in value: errors.append(f'{path}/{k}: required')
        for k,v in value.items():
            if k in props: errors += schema_errors(v,props[k],root,f'{path}/{k}')
            elif schema.get('additionalProperties',True) is False: errors.append(f'{path}/{k}: unexpected field')
            elif isinstance(schema.get('additionalProperties'),dict):
                errors += schema_errors(v,schema['additionalProperties'],root,f'{path}/{k}')
    if isinstance(value,list):
        if len(value)<schema.get('minItems',0): errors.append(f'{path}: too few items')
        for i,v in enumerate(value): errors += schema_errors(v,schema.get('items',{}),root,f'{path}/{i}')
    if isinstance(value,str):
        if 'pattern' in schema and re.search(schema['pattern'],value) is None:
            errors.append(f'{path}: invalid format')
        if len(value.strip())<schema.get('minLength',0): errors.append(f'{path}: empty text')
        if schema.get('format')=='date':
            try:
                if len(value)!=10 or dt.date.fromisoformat(value).isoformat()!=value: raise ValueError()
            except ValueError: errors.append(f'{path}: expected ISO date YYYY-MM-DD')
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if 'minimum' in schema and value<schema['minimum']: errors.append(f'{path}: below minimum')
        if 'maximum' in schema and value>schema['maximum']: errors.append(f'{path}: above maximum')
    return errors

def library():
    folder=ROOT/'references'/'training-library'
    return {x['id']:x for name in ('exercises.json','training-units.json') for x in read_json(folder/name)}
