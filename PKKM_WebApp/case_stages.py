"""Explicit case-stage classification; preserve unknown legacy status verbatim."""
import json
import re
from pathlib import Path
SCHEMA=json.loads((Path(__file__).parent/'case_stages.json').read_text())
STAGES=SCHEMA['stages']
REVIEW=SCHEMA['review']
def normalized(value):return ' '.join(re.sub(r'[^\w\s]',' ',value.casefold()).split())
ALIASES={normalized(value):value for value in STAGES}
ALIASES.update({normalized(key):value for key,value in SCHEMA['aliases'].items()})
def handling_stage(status):return ALIASES.get(normalized(status or ''))
def stage_counts(records):
    counts={label:0 for label in STAGES};review=0
    for item in records:
        label=handling_stage(item.status)
        if label:counts[label]+=1
        else:review+=1
    return {'stages':counts,'stageReview':review}

MIGRATIONS={normalized(key):value for key,value in SCHEMA['migrations'].items()}
def apply_case_mapping(c,ident):
    row=c.execute('SELECT payload FROM ppkt_cases WHERE id=?',(ident,)).fetchone()
    if not row:return False
    original=json.loads(row['payload'])
    mapping=MIGRATIONS.get(normalized(original.get('status') or ''))
    if not mapping:return False
    updated=dict(original,status=mapping['status'])
    position=mapping.get('position')
    existing=original.get('positionNotes') or ''
    if position and position.casefold() not in [item.strip().casefold() for item in re.split(r'[;\n|]',existing)]:
        updated['positionNotes']=(existing.rstrip()+'\n'+position).strip()
    after=json.dumps(updated,ensure_ascii=False)
    # Compare against the source read, so another worker/user update is not overwritten.
    changed=c.execute('UPDATE ppkt_cases SET payload=? WHERE id=? AND payload=?',(after,ident,row['payload'])).rowcount
    if changed:
        c.execute('INSERT INTO ppkt_status_mapping_history(case_id,before_payload,after_payload) VALUES(?,?,?)',(ident,row['payload'],after))
    return bool(changed)

def initialize_status_mapping(c):
    c.execute('CREATE TABLE IF NOT EXISTS ppkt_status_mapping_history(id INTEGER PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES ppkt_cases(id) ON DELETE CASCADE,before_payload TEXT NOT NULL,after_payload TEXT NOT NULL,at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
    ids=[row['id'] for row in c.execute('SELECT id FROM ppkt_cases')]
    for ident in ids:apply_case_mapping(c,ident)
