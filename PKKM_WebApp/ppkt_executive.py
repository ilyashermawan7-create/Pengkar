"""Presentation aggregates; preserve original records and avoid inferred case outcomes."""
import re

def faculty_label(item):
    raw=' '.join(item.reportedFaculty.split())
    institution=' '.join(item.reportedInstitution.casefold().split())
    if institution and 'telkom' not in institution:return 'Eksternal'
    key=raw.casefold()
    if 'luar telkom' in key or key=='eksternal':return 'Eksternal'
    aliases={'fakultas ekonomi dan bisnis':'FEB','fakultas teknik elektro':'FTE','fakultas informatika':'FIF','fakultas rekayasa industri':'FRI','fakultas ilmu terapan':'FIT','fakultas industri kreatif':'FIK','fakultas komunikasi dan bisnis':'FKS/FKB','fakultas komunikasi dan ilmu sosial':'FKS/FKB','fks':'FKS/FKB','fkb':'FKS/FKB'}
    if key in aliases:return aliases[key]
    return raw or 'Belum diisi'

def recommendation(item):
    status=item.status.casefold()
    return bool(re.search(r'rekomendasi.*sanksi|menentukan sanksi|penentuan sanksi|penetapan sanksi',status))

def executive_stats(records,bucket):
    result={'recommendations':0,'activeInvestigation':0,'reportedFaculties':{},'sexualYears':{}}
    for item in records:
        faculty=faculty_label(item)
        result['reportedFaculties'][faculty]=result['reportedFaculties'].get(faculty,0)+1
        if 'seksual' in item.category.casefold():
            year=str(item.year) if item.year else 'Belum diisi';result['sexualYears'][year]=result['sexualYears'].get(year,0)+1
        if bucket(item.status)=='Dalam proses':
            if recommendation(item):result['recommendations']+=1
            else:result['activeInvestigation']+=1
    return result
