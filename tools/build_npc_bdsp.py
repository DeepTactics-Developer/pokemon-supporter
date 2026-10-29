"""BDSP 주요 NPC 엔트리 → npc/23.json

출처
  - Bulbapedia 위키 원문(action=raw): 포켓몬·레벨·특성·지닌 물건·기술 (구조화된 템플릿)
  - Serebii BDSP 페이지: 성격 (Bulbapedia엔 없음) + 기술·물건 교차 확인
  - PokeAPI: 모든 이름이 실제 존재하는지 검사, 물건 한글 이름

사용법: python build_npc_bdsp.py <bulbapedia raw 폴더> <serebii html 폴더> <출력 json>
"""
import json, re, sys, urllib.request
from pathlib import Path

BULBA, SERE, OUT = map(Path, sys.argv[1:4])

# (파일명, id, 한글 이름, 역할, 설명)
TRAINERS = [
    ('Roark', 'roark', '강석', '체육관 관장', '1 · 바위 · 무쇠시티'),
    ('Gardenia', 'gardenia', '유채', '체육관 관장', '2 · 풀 · 영원시티'),
    ('Maylene', 'maylene', '자두', '체육관 관장', '3 · 격투 · 장막시티'),
    ('Crasher_Wake', 'wake', '맥시', '체육관 관장', '4 · 물 · 들판시티'),
    ('Fantina', 'fantina', '멜리사', '체육관 관장', '5 · 고스트 · 축복시티'),
    ('Byron', 'byron', '동관', '체육관 관장', '6 · 강철 · 운하시티'),
    ('Candice', 'candice', '무청', '체육관 관장', '7 · 얼음 · 선단시티'),
    ('Volkner', 'volkner', '전진', '체육관 관장', '8 · 전기 · 물가시티'),
    ('Aaron', 'aaron', '충호', '사천왕', '벌레'),
    ('Bertha', 'bertha', '들국화', '사천왕', '땅'),
    ('Flint', 'flint', '대엽', '사천왕', '불꽃'),
    ('Lucian', 'lucian', '오엽', '사천왕', '에스퍼'),
    ('Cynthia', 'cynthia', '난천', '챔피언', ''),
    ('Barry', 'barry', '용식', '라이벌', '스타터에 따라 엔트리가 달라요'),
    ('Mars', 'mars', '마스', '갤럭시단', '간부'),
    ('Jupiter', 'jupiter', '주피터', '갤럭시단', '간부'),
    ('Saturn', 'saturn', '새턴', '갤럭시단', '간부'),
    ('Cyrus', 'cyrus', '태홍', '갤럭시단', '보스'),
]
STARTER = {'Turtwig': '모부기', 'Chimchar': '불꽃숭이', 'Piplup': '팽도리'}
# 소제목 → 한글 (없는 소제목이 나오면 에러로 알려줌)
LABEL = {
    'Gym battle': '체육관', 'Rematch': '재대전',
    'First match': '첫 대전', 'Rematch (before Stark Mountain)': '재대전 1 (스텔라산 이전)',
    'Rematch (after Stark Mountain)': '재대전 2 (스텔라산 이후)',
    'Champion battle': '챔피언전',
    'First battle': '1번째', 'Second battle': '2번째', 'Third battle': '3번째',
    'Fourth battle': '4번째', 'Fifth battle': '5번째',
    'Weekend battles': '주말 재대전 (배틀존)', 'After entering the Hall of Fame 20 times': '주말 재대전 (전당 등록 20회 이후)',
}
ORD = {'First': '1번째', 'Second': '2번째', 'Third': '3번째', 'Fourth': '4번째', 'Fifth': '5번째'}
PARTNER = {'Jupiter': '주피터', 'Mars': '마스'}


def label_of(t):
    if t in LABEL:
        return LABEL[t]
    m = re.match(r'(\w+) battle \(Multi Battle with (\w+)\)$', t)
    if m and m.group(1) in ORD and m.group(2) in PARTNER:
        return f'{ORD[m.group(1)]} ({PARTNER[m.group(2)]}와 멀티배틀)'
    return None
SKIP = ('Battle Tower', 'Master Class', 'Multi Battle with the player')
# 재대전·사천왕·챔피언은 노력치 투자됨 (정확한 배분은 공개 정보 없음)
TRAINED_ROLES = {'사천왕', '챔피언'}

slug = lambda s: re.sub(r'[^a-z0-9-]', '', s.lower().replace(' ', '-').replace('é', 'e')).strip('-')


def bdsp_section(text):
    lines = text.split('\n')
    start = next((i for i, l in enumerate(lines) if re.match(r'^={3,4}\{\{g\|Brilliant Diamond and Shining Pearl\}\}={3,4}\s*$', l)), None)
    if start is None:
        raise SystemExit('BDSP section not found')
    lvl = len(re.match(r'^=+', lines[start]).group())
    out = []
    for l in lines[start + 1:]:
        m = re.match(r'^(=+)[^=]', l)
        if m and len(m.group(1)) <= lvl:
            break
        out.append(l)
    return out


def clean(v):
    """위키 템플릿 정리: {{tt|현재값|설명}} → 현재값 (예전 버전 값 설명은 버림), [[a|b]] → b"""
    v = re.sub(r'\{\{tt\|([^|}]*)\|[^}]*\}\}', r'\1', v)
    v = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', v)
    return v.strip()


def fields(block):
    d = {}
    # "| key = value" 단위로 자름. 템플릿 안의 파이프({{PlayerChoice|0390|Chimchar}})는 뒤에 "key ="가 없어서 안 잘림
    for p in re.split(r'\|(?=\s*\w+\s*=)', block):
        if '=' in p:
            k, v = p.split('=', 1)
            d[k.strip()] = clean(v)
    return d


def parse_bulba(path, trainer):
    lines = bdsp_section(path.read_text(encoding='utf-8'))
    head, sub, parties, i = '', '', [], 0
    while i < len(lines):
        l = lines[i]
        m = re.match(r'^(=+)\s*(.*?)\s*=+\s*$', l)
        if m:
            t = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', m.group(2))
            if len(m.group(1)) == 5:
                head, sub = t, ''
            else:
                sub = t
            i += 1
            continue
        # {{Party/2}}는 멀티배틀(두 트레이너): {{Party/2/div}} 앞까지가 이 페이지 트레이너의 포켓몬
        if l.rstrip() in ('{{Party', '{{Party/2'):
            j = i
            while lines[j].strip() != '}}':
                j += 1
            party = fields('\n'.join(lines[i + 1:j]))
            # 멀티배틀 표에서 이 트레이너가 뒤쪽(name2)에 적혀 있으면 div 뒤가 이 트레이너 몫
            first = trainer.replace('_', ' ') in party.get('name', '')
            mons, i, mine = [], j + 1, first or l.rstrip() == '{{Party'
            while not lines[i].startswith('{{Party/end'):
                if lines[i].startswith('{{Party/2/div'):
                    mine = not first
                if mine and lines[i].startswith('{{Pokémon'):
                    j = i
                    while lines[j].strip() != '}}':
                        j += 1
                    mons.append(fields('\n'.join(lines[i + 1:j])))
                    i = j
                i += 1
            parties.append((head, sub, party, mons))
        i += 1
    return parties


def parse_serebii():
    tables = []
    for f in sorted(SERE.glob('*.html')):
        h = f.read_text(encoding='utf-8', errors='replace')
        # 표 안에 작은 표가 중첩돼 있어서 </table>로 자르지 않고 다음 트레이너 표까지를 한 덩어리로 봄
        for t in h.split('<table class="trainer">')[1:]:
            first_row = t.split('</tr>')[0]
            species = re.findall(r'alt="([^"]+)"', first_row)
            levels = [int(x) for x in re.findall(r'class="level"[^>]*>Level (\d+)', t)]
            natures = re.findall(r'<b>Nature</b>:<br />\s*([A-Za-z]+)', t)
            items = [re.findall(r'title="([^"]+)"', c)[:1] for c in re.split(r'<b>Hold Item</b>', t)[1:]]
            moves = [re.findall(r'attackdex[^"]*">([^<]+)</a>', c) for c in re.split(r'<b>Attacks</b>', t)[1:]]
            tables.append({'file': f.stem, 'species': [slug(s) for s in species], 'levels': levels,
                           'natures': natures, 'items': [slug(x[0]) if x else '' for x in items],
                           'moves': [[slug(m) for m in ms] for ms in moves]})
    return tables


def check_names(kind, names):
    """PokeAPI에 없는 이름 목록 + {이름: 한글}"""
    names = sorted(n for n in names if n)
    table = {'pokemon': 'pokemon_v2_pokemon', 'move': 'pokemon_v2_move', 'ability': 'pokemon_v2_ability', 'item': 'pokemon_v2_item'}[kind]
    ko = {'item': 'pokemon_v2_itemnames', 'move': 'pokemon_v2_movenames', 'ability': 'pokemon_v2_abilitynames', 'pokemon': None}[kind]
    q = '{%s(where:{name:{_in:%s}}){name %s}}' % (table, json.dumps(names), f'{ko}(where:{{language_id:{{_eq:3}}}}){{name}}' if ko else '')
    req = urllib.request.Request('https://beta.pokeapi.co/graphql/v1beta', data=json.dumps({'query': q}).encode(), headers={'content-type': 'application/json', 'user-agent': 'pokemon-supporter-build'})
    rows = json.load(urllib.request.urlopen(req))['data'][table]
    found = {r['name']: (r[ko][0]['name'] if ko and r[ko] else '') for r in rows}
    return [n for n in names if n not in found], found


# 용식은 플레이어 스타터의 상성 우위 스타터를 가짐 → 용식의 스타터 계열로 플레이어 스타터를 판별
BARRY_LINE = {'turtwig': 'Piplup', 'grotle': 'Piplup', 'torterra': 'Piplup', 'chimchar': 'Turtwig', 'monferno': 'Turtwig',
              'infernape': 'Turtwig', 'piplup': 'Chimchar', 'prinplup': 'Chimchar', 'empoleon': 'Chimchar'}


def find_serebii(team):
    """같은 엔트리의 Serebii 표: 순서·레벨 일치 → 순서만 일치 → 구성만 일치 순으로 찾음"""
    sp, lv = [t['s'] for t in team], [t['lv'] for t in team]
    tests = [(lambda t: (t['species'], t['levels']) == (sp, lv), ''),
             (lambda t: t['species'] == sp, '레벨 다름'),
             (lambda t: sorted(zip(t['species'], t['levels'])) == sorted(zip(sp, lv)), '순서 다름')]
    for test, why in tests:
        k = next((k for k, t in enumerate(sere) if k not in used and test(t)), None)
        if k is not None:
            return k, why
    return None, ''


npcs, problems, sere = [], [], parse_serebii()
used = set()
for fname, nid, ko, role, note in TRAINERS:
    battles = []
    for head, sub, party, mons in parse_bulba(BULBA / f'{fname}.txt', fname):
        if any(s in head or s in sub for s in SKIP):
            continue
        label = label_of(sub) if sub else label_of(head)
        if not label:
            raise SystemExit(f'{fname}: 모르는 소제목 "{head}" / "{sub}"')
        team = [{'s': slug(m['pokemon']), 'lv': int(m['level']), 'ab': slug(m.get('ability', '')),
                 'it': '' if slug(m.get('held', '')) == 'none' else slug(m.get('held', '')), 'mv': [slug(m[f'move{k}']) for k in range(1, 5) if m.get(f'move{k}')]} for m in mons]
        cap = re.search(r'PlayerChoice\|\d+\|(\w+)', party.get('caption', ''))
        if nid == 'barry':
            starter = next(BARRY_LINE[t['s']] for t in team if t['s'] in BARRY_LINE)
            if cap and cap.group(1) != starter:
                problems.append(f'[스타터 표시 다름] {ko} {label}: 표={cap.group(1)} 엔트리 판별={starter}')
            label += f' · 내 스타터 {STARTER[starter]}'
        elif cap:
            label += f' · 내 스타터 {STARTER[cap.group(1)]}'
        # Serebii 표에서 성격을 가져오고 기술·물건 대조 (같은 표를 두 번 쓰지 않음)
        match, why = find_serebii(team)
        if match is None:
            problems.append(f'[성격 없음] {ko} {label}: Serebii에 같은 엔트리 없음 {[t["s"] for t in team]}')
        else:
            used.add(match)
            t = sere[match]
            if why:
                problems.append(f'[{why}] {ko} {label}: Bulbapedia {[(p["s"], p["lv"]) for p in team]} / Serebii {list(zip(t["species"], t["levels"]))} → Bulbapedia 기준')
            by = {s: k for k, s in enumerate(t['species'])}
            for p in team:
                k = by[p['s']]
                nat, it, mv = t['natures'][k], t['items'][k], t['moves'][k]
                p['nat'] = nat.lower()
                alt = {}
                if it != p['it']:
                    alt['it'] = it
                if mv and sorted(mv) != sorted(p['mv']):
                    alt['mv'] = mv
                if alt:
                    p['alt'] = alt  # 출처가 다른 부분: 사이트에서 "Serebii에는 …"으로 함께 표시
                    problems.append(f'[출처 다름] {ko} {label} {p["s"]}: Bulbapedia 물건={p["it"]} 기술={p["mv"]} / Serebii {alt}')
        trained = role in TRAINED_ROLES or '재대전' in label
        battles.append({'label': label, 'trained': trained, 'team': team})
    npcs.append({'id': nid, 'name': ko, 'role': role, 'note': note, 'battles': battles})

# 이름 검사 (PokeAPI)
allp = [p for n in npcs for b in n['battles'] for p in b['team']]
items_ko = {}
alts = [p['alt'] for p in allp if 'alt' in p]
for kind, names in [('pokemon', {p['s'] for p in allp}), ('move', {m for p in allp for m in p['mv']} | {m for a in alts for m in a.get('mv', [])}),
                    ('ability', {p['ab'] for p in allp}), ('item', {p['it'] for p in allp} | {a['it'] for a in alts if a.get('it')})]:
    missing, found = check_names(kind, names)
    for n in missing:
        problems.append(f'[PokeAPI에 없음] {kind}: {n}')
    if kind == 'item':
        items_ko = found

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({'game': 23, 'source': 'Bulbapedia (포켓몬·특성·물건·기술) + Serebii (성격), 교차 확인',
                           'items': items_ko, 'npcs': npcs}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(f'NPC {len(npcs)}명, 대전 {sum(len(n["battles"]) for n in npcs)}개, 포켓몬 {len(allp)}마리')
for n in npcs:
    print(' ', n['name'], [b['label'] for b in n['battles']])
print(f'\n확인 필요 {len(problems)}건')
for p in problems:
    print(' ', p)
