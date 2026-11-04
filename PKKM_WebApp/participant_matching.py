"""Conservative activity matching for pending participants; never uses fuzzy similarity."""
import hashlib
import unicodedata


def title_key(value):
    value=unicodedata.normalize('NFKC',value or '').casefold().replace('&',' and ')
    words=''.join(character if character.isalnum() else ' ' for character in value)
    return ' '.join('dan' if word=='and' else word for word in words.split())


def group_key(record_id,item):
    title=title_key(item.namaKegiatan)
    # Without an activity name we cannot infer that two people belong to one event.
    identity=(title or 'unnamed:'+record_id)+'|'+item.tanggalKegiatan
    return hashlib.sha256(identity.encode()).hexdigest()


def activity_index(activities):
    index={}
    for activity in activities:
        key=title_key(activity['nama_kegiatan'])
        if key:index.setdefault(key,[]).append(activity)
    return index


def match(item,index):
    key=title_key(item.namaKegiatan)
    if not key:return None,'blank'
    candidates=index.get(key,[])
    if not candidates:return None,'unmatched'
    if item.tanggalKegiatan:
        dated=[activity for activity in candidates if activity['tanggal']==item.tanggalKegiatan]
        if len(dated)==1:return dated[0],'matched'
        if not dated:return None,'date_conflict'
        return None,'ambiguous'
    if len(candidates)==1:return candidates[0],'matched'
    return None,'ambiguous'
