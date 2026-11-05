"""Small dashboard statistics, computed without serializing individual records."""
import collections
import json
import math

def dashboard_stats(c,ids):
    ids=sorted(set(ids))
    questions=[{'sum':0.0,'count':0} for _ in range(20)]
    result={'uniqueNim':0,'faculties':[],'surveys':{'totalResponses':0,'responses':0,'items':questions}}
    if not ids:return result
    placeholders=','.join('?' for _ in ids)
    people={}
    for row in c.execute(f'SELECT s.nim,s.fakultas FROM activity_participants p JOIN students s ON s.nim=p.nim WHERE p.activity_id IN ({placeholders})',ids):
        people['nim:'+row['nim']] = (row['nim'],row['fakultas'])
    for row in c.execute(f'SELECT d.record_key,d.nim,d.fakultas FROM activity_unidentified_participants p JOIN student_directory d ON d.record_key=p.record_key WHERE p.activity_id IN ({placeholders})',ids):
        people['nim:'+row['nim'] if row['nim'] else 'directory:'+row['record_key']]=(row['nim'],row['fakultas'])
    result['uniqueNim']=sum(bool(nim) for nim,_ in people.values())
    faculties=collections.Counter(faculty or 'Belum diisi' for _,faculty in people.values())
    result['faculties']=sorted(faculties.items(),key=lambda pair:-pair[1])
    for row in c.execute(f'SELECT payload FROM survey_responses WHERE activity_id IN ({placeholders})',ids):
        result['surveys']['totalResponses']+=1
        answers=json.loads(row['payload']).get('answers')
        if not isinstance(answers,list) or len(answers)!=20:continue
        result['surveys']['responses']+=1
        for index,value in enumerate(answers):
            if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and 1<=value<=5:
                questions[index]['sum']+=value;questions[index]['count']+=1
    return result
