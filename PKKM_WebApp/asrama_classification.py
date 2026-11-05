"""Conservative suggestions for reviewing old dorm activities; no fabricated defaults."""
import re
import unicodedata
CATEGORIES=('Adaptif','Spiritual','Akademik','Sosial')
ALIASES={'adaptif':'Adaptif','adaktif':'Adaptif','spiritual':'Spiritual','spritual':'Spiritual','akademik':'Akademik','sosial':'Sosial'}
def normalize(value):
    return ' '.join(unicodedata.normalize('NFKC',value or '').casefold().split())
def canonical(value):return ALIASES.get(normalize(value))
RULES={
 'Adaptif':r'\badaptasi\b|\borientasi\b|\bcheck[ -]?in\b|\blife skill\b|\bk3l?\b|\bkeselamatan\b|\bhospitality\b|\bmanajemen waktu\b|\bpengelolaan diri\b|\binformasi asrama\b|\btipe tipe penghuni\b|\bsidak\b|\btata tertib\b|\btata cara tinggal\b',
 'Spiritual':r'\biftar\b|\bsahur\b|\bbuka puasa\b|\bpuasa\b|\bramadan\b|\bramadhan\b|\btarawih\b|\bkajian agama\b|\bshalat\b|\bsalat\b|\bpengajian\b|\bibadah\b|\brohani\b|\bhalal bi[ -]?halal\b',
 'Akademik':r'\bstrategi belajar\b|\bteknik belajar\b|\bstudy skills?\b|\bmanajemen belajar\b|\bbelajar efektif\b|\bpenulisan ilmiah\b|\bkarya ilmiah\b|\bpersiapan ujian\b|\bprestasi akademik\b|\btutorial akademik\b|\bbimbingan belajar\b',
 'Sosial':r'\bolahraga\b|\bolympic\b|\bfutsal\b|\bbasket\b|\bbadminton\b|\bbulu tangkis\b|\bbakti sosial\b|\bpengabdian masyarakat\b|\bkerja bakti\b|\bgotong royong\b|\bkepemimpinan\b|\bleadership\b|\bstruktur organisasi\b|\bteam building\b|\bpeer counsel(?:or|ing)\b|\bhelping conversation\b|\bserah terima jabatan\b|\bfirst meet\b',
}
def suggest(name,kind='',description=''):
    # Prefer explicit title evidence; use additional descriptions only when the title is silent.
    for text in (normalize(name),normalize(' '.join((kind or '',description or '')))):
        matches=[(category,re.search(pattern,text)) for category,pattern in RULES.items()]
        matches=[(category,match.group(0)) for category,match in matches if match]
        if len(matches)==1:return matches[0][0],f'Kata kunci: {matches[0][1]}'
        if len(matches)>1:return None,'Memuat lebih dari satu asas; pilih kategori berdasarkan tujuan utama kegiatan'
    return None,'Judul/uraian belum cukup jelas; pilih kategori secara manual'
def is_dorm(row,details):
    if details.get('navigationGroup')=='ppk-telu':return False
    if row['program']=='Asrama' or details.get('navigationGroup')=='asrama':return True
    text=normalize(' '.join((row['nama_kegiatan'],row['kategori'],details.get('urusan',''),details.get('jenis',''))))
    if re.search(r'\bppkpt\b|\bppks\b|kekerasan',text):return False
    return bool(re.search(r'\basrama\b|\bresidents?\b|\bresiden\b|\bsr\b',text))

def categorize_legacy(c):
    """Apply reversible, idempotent keyword assignments at startup; leave ambiguous rows for review."""
    import json
    tables={row['name'] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'activities','audit'}.issubset(tables):return 0
    if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
    c.execute('CREATE TABLE IF NOT EXISTS asrama_category_history(id INTEGER PRIMARY KEY,activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,old_category TEXT NOT NULL,new_category TEXT NOT NULL,changed_by INTEGER,at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
    reviewed={row['activity_id'] for row in c.execute('SELECT DISTINCT activity_id FROM asrama_category_history')}
    rows=list(c.execute('SELECT a.*,d.payload AS details FROM activities a LEFT JOIN activity_details d ON d.activity_id=a.id'))
    updated=0
    for row in rows:
        if row['id'] in reviewed or row['kategori'] in CATEGORIES:continue
        details=json.loads(row['details']) if row['details'] else {}
        if not is_dorm(row,details):continue
        category=canonical(row['kategori'])
        if not category:category,_=suggest(row['nama_kegiatan'],details.get('jenis',''),row['laporan'])
        if not category:continue
        c.execute('INSERT INTO asrama_category_history(activity_id,old_category,new_category,changed_by) VALUES(?,?,?,NULL)',(row['id'],row['kategori'],category))
        c.execute('UPDATE activities SET kategori=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(category,row['id']))
        c.execute("INSERT INTO audit(user_id,action,entity,entity_id) VALUES(NULL,'categorize_asrama_startup','activity',?)",(row['id'],))
        updated+=1
    return updated
