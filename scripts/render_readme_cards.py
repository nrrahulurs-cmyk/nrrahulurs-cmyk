#!/usr/bin/env python3
"""Render self-contained animated GitHub profile SVG cards.

    python scripts/render_readme_cards.py
    GITHUB_TOKEN=... python scripts/render_readme_cards.py --refresh
    STATIC=1 python scripts/render_readme_cards.py

Uses pyftsubset to embed Google Fonts subsets as WOFF data URIs directly in SVG.
A local open-source font fallback supports offline previews; GitHub Actions uses
Instrument Serif and Inter from official Google Fonts repositories.
"""
from __future__ import annotations
import argparse
import base64
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html import escape
import mimetypes
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / 'cards'
DATA_FILE = ROOT / 'data' / 'contributions.json'
USERNAME = 'nrrahulurs-cmyk'
NAME = 'Rahul Urs'
INK, MUTED, PAPER, BORDER = '#202020', '#68645F', '#F8F6F0', '#DEDAD1'
BLUE, RED, GOLD = '#325BE8', '#E26B50', '#E5AF28'
STATIC = os.getenv('STATIC', '0') == '1'
FONTS = [
    ('Editorial', 'https://raw.githubusercontent.com/google/fonts/main/ofl/instrumentserif/InstrumentSerif-Regular.ttf',
     '/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf'),
    ('Interface', 'https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz,wght%5D.ttf',
     '/usr/share/fonts/truetype/lato/Lato-Regular.ttf'),
]
REPOS = [
    ('timora','Timora','A smarter way to plan campus life.','ACADEMIC SCHEDULING / TYPESCRIPT','Timetables · rooms · faculty',BLUE),
    ('notegen','NoteGen AI','From handwriting to clarity.','DOCUMENT AI / PYTHON','Recognize · structure · export',RED),
    ('glitchbound','GlitchBound','An open city. A world to explore.','CYBERPUNK GAME / THREE.JS','Explore · drive · discover',GOLD),
    ('ciirc','CIIRC Admin OS','Research administration, connected.','RESEARCH CONSOLE / NEXT.JS','Projects · grants · governance',BLUE),
]

def E(value): return escape(str(value), quote=True)

def font_faces():
    rules = []
    with TemporaryDirectory() as temp:
        for family, url, fallback in FONTS:
            source = Path(temp) / (family+'.ttf')
            target = Path(temp) / (family+'.woff')
            try:
                data = urlopen(Request(url, headers={'User-Agent':'profile-cards/1.0'}), timeout=12).read()
                if data[:4] not in (b'\x00\x01\x00\x00', b'OTTO', b'true', b'ttcf'):
                    raise ValueError('Not a font')
                source.write_bytes(data)
            except Exception as ex:
                if not Path(fallback).is_file():
                    raise RuntimeError(f'Could not load Google font {family}: {ex}') from ex
                source = Path(fallback)
                print(f'Using locally installed preview font for {family}',file=sys.stderr)
            subprocess.run([
                'pyftsubset', str(source), '--output-file='+str(target), '--flavor=woff',
                '--unicodes=U+0020-007E,U+00B7,U+2013-2014,U+2018-2019,U+201C-201D,U+2022,U+2192,U+2197',
                '--layout-features=*','--no-hinting'
            ], check=True, capture_output=True, text=True)
            encoded = base64.b64encode(target.read_bytes()).decode('ascii')
            rules.append(f"@font-face{{font-family:'{family}';src:url(data:font/woff;base64,{encoded}) format('woff');}}")
    return ''.join(rules)

def css(fontfaces):
    motion = '''
    @keyframes rise{0%{opacity:0;transform:translateY(16px)}100%{opacity:1;transform:translateY(0)}}
    @keyframes grow{0%{opacity:.1;transform:scaleY(.05)}100%{opacity:1;transform:scaleY(1)}}
    @keyframes swing{0%{opacity:0;transform:translateY(28px) rotate(-4deg)}
      72%{opacity:1;transform:translateY(-3px) rotate(1deg)}100%{opacity:1;transform:none}}
    @keyframes cellReveal{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:none}}
    @keyframes nudge{50%{transform:translate(3px,-3px)}}
    .rise{opacity:0;animation:rise .75s cubic-bezier(.19,1,.22,1) both;animation-delay:var(--d,0s)}
    .bar{transform-box:fill-box;transform-origin:center bottom;animation:grow .68s cubic-bezier(.19,1,.22,1) both;animation-delay:var(--d,0s)}
    .tileEnter{opacity:0;animation:swing .75s cubic-bezier(.2,.82,.24,1) both;animation-delay:var(--d,0s)}
    .cell{opacity:0;animation:cellReveal .4s ease-out both;animation-delay:var(--d,0s)}
    .arrow{animation:nudge 3s ease-in-out infinite 3s}
    @media(prefers-reduced-motion:reduce){
       .rise,.bar,.tileEnter,.cell,.arrow{animation:none!important;opacity:1!important;transform:none!important}
       .shine-layer{display:none!important}
    }
    '''
    static='''.rise,.bar,.tileEnter,.cell,.arrow{animation:none!important;opacity:1!important;transform:none!important}
    .shine-layer{display:none!important}'''
    return f'''<style><![CDATA[{fontfaces}
      text{{font-family:'Interface',Arial,sans-serif;fill:{INK}}}
      .serif{{font-family:'Editorial',Georgia,serif}}
      .muted{{fill:{MUTED}}}
      .label{{font-size:11px;letter-spacing:1.9px;font-weight:700}}
      {static if STATIC else motion}
    ]]></style>'''

def svg(w,h,body,fonts,bg=PAPER):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'viewBox="0 0 {w} {h}" role="img">{css(fonts)}'
           f'<rect width="{w}" height="{h}" rx="13" fill="{bg}"/>{body}</svg>\n')

def line(x,y,x2,color=BORDER,width=1):
    return f'<path d="M{x} {y}H{x2}" stroke="{color}" stroke-width="{width}"/>'

def T(x,y,value,size,cls='',color=None,extra=''):
    if color and 'style="' in extra:
        extra=extra.replace('style="', f'style="fill:{color};', 1)
        fill=''
    else:
        fill=f' style="fill:{color}"' if color else ''
    return f'<text x="{x}" y="{y}" font-size="{size}" class="{cls}"{fill} {extra}>{E(value)}</text>'

def portrait_or_monogram():
    """Embed an optional local portrait; no external image request at README render time.

    Set PORTRAIT_PATH or put assets/portrait.png in the profile repository.
    JPEG and PNG are supported. A small file (<2 MiB) keeps the SVG portable.
    """
    path = Path(os.environ.get('PORTRAIT_PATH',str(ROOT/'assets'/'portrait.png')))
    if path.is_file():
        mime,_=mimetypes.guess_type(str(path))
        if mime not in ('image/png','image/jpeg'):
            raise ValueError('Portrait must be a PNG or JPEG')
        content=path.read_bytes()
        if len(content)>2_000_000:raise ValueError('Portrait is larger than 2 MB')
        encoded=base64.b64encode(content).decode('ascii')
        return (f'<defs><clipPath id="portraitMask"><circle cx="805" cy="196" r="70"/></clipPath></defs>'
                f'<image x="735" y="126" width="140" height="140" preserveAspectRatio="xMidYMid slice" '
                f'href="data:{mime};base64,{encoded}" clip-path="url(#portraitMask)"/>')
    return '<circle cx="805" cy="196" r="71" fill="'+BLUE+'"/>'+T(765,225,'R',91,'serif rise',color='white',extra='style="--d:.52s"')

def hero(fonts):
    s=[line(37,59,923),T(38,40,'R / U',23,color=BLUE),T(922,38,'GITHUB  /  PORTFOLIO',11,'label muted',extra='text-anchor="end"'),
       T(40,135,"Hello, I'm",26,'serif rise',extra='style="--d:.05s"'),
       T(36,223,NAME,86,'serif rise',extra='style="--d:.16s"'),
       T(40,263,'Building useful tools, curious experiments & digital worlds.',18,'rise',extra='style="--d:.34s"'),
       line(39,286,625),T(40,319,'SOFTWARE  ·  AI  ·  CREATIVE CODING',12,'label muted rise',extra='style="--d:.48s"'),
       '<rect x="688" y="82" width="235" height="228" rx="11" fill="#EEEAE1"/>']
    for i in range(4):
        s.append(f'<circle cx="805" cy="196" r="{35+i*22}" fill="none" stroke="#D2CBBF" stroke-width="1"/>')
    s += [portrait_or_monogram(), f'<circle cx="900" cy="97" r="7" fill="{RED}"/><circle cx="703" cy="291" r="5" fill="{GOLD}"/>']
    if not STATIC:
        s.append(f'''<defs><linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
             <stop offset="0" stop-color="{BLUE}" stop-opacity="0"/>
             <stop offset=".5" stop-color="#C8D3FF" stop-opacity=".6"/>
             <stop offset="1" stop-color="{BLUE}" stop-opacity="0"/>
             <animate attributeName="gradientTransform" from="-2 0" to="2 0"
                dur="4s" begin="3s" repeatCount="indefinite" />
             </linearGradient></defs>
             <text x="36" y="223" font-size="86" class="serif shine-layer"
                fill="url(#sweep)">{E(NAME)}</text>''')
    return svg(960,340,''.join(s),fonts)

def activity_data():
    try: obj=json.loads(DATA_FILE.read_text())
    except FileNotFoundError: return []
    days=[]
    for item in obj.get('days',[]):
        try: days.append((date.fromisoformat(item['date']),max(0,int(item.get('count',item.get('contributionCount',0))))) )
        except (ValueError,KeyError,TypeError): pass
    return sorted(days)

def statistics(days):
    if not days:return None
    counts=dict(days)
    today=date.today()
    cur=today if counts.get(today,0)>0 else today-timedelta(days=1)
    streak=0
    while counts.get(cur,0)>0:
        streak+=1;cur-=timedelta(days=1)
    monthly=defaultdict(int)
    for d,n in days: monthly[d.strftime('%Y-%m')]+=n
    return {'total':sum(n for _,n in days),'active':sum(n>0 for _,n in days),
            'streak':streak,'best':max(days,key=lambda item:(item[1],item[0])),
            'months':monthly}

def graph(fonts,days):
    stats=statistics(days)
    s=[T(38,42,'A year in commits',30,'serif rise',extra='style="--d:.68s"'),
       T(923,36,'LIVE ACTIVITY' if stats else 'AWAITING FIRST SYNC',11,'label muted',extra='text-anchor="end"'),line(38,55,922)]
    counts=dict(days);today=date.today()
    start=today-timedelta(days=(today.weekday()+1)%7)-timedelta(weeks=52)
    for col in range(53):
        for row in range(7):
            day=start+timedelta(days=col*7+row)
            if day>today:continue
            n=counts.get(day,0)
            color=('#E6E2D9' if not n else '#CED8FD' if n==1 else '#9DB5FF' if n<=3 else '#6787F2' if n<=7 else BLUE)
            x=51+col*16.3;y=72+row*16
            s.append(f'<rect x="{x:.1f}" y="{y}" width="13" height="13" rx="2.3" fill="{color}" class="cell" style="--d:{.82+col*.014+row*.01:.3f}s"/>')
    s.append(T(51,204,'LAST 365 DAYS / PUBLIC CONTRIBUTIONS' if stats else 'ACTIVITY APPEARS AFTER THE FIRST SCHEDULED SYNC',11,'label muted'))
    s.append(T(782,204,'LESS',10,'label muted'))
    for i,col in enumerate(('#E6E2D9','#CED8FD','#9DB5FF','#6787F2',BLUE)):
        s.append(f'<rect x="{817+i*15}" y="194" width="11" height="11" rx="2" fill="{col}"/>')
    s.append(T(923,204,'MORE',10,'label muted',extra='text-anchor="end"'))
    return svg(960,221,''.join(s),fonts)

def monthly(fonts,days):
    s=[T(38,41,'The rhythm of building',32,'serif rise',extra='style="--d:1.14s"'),
       T(38,70,'CONTRIBUTIONS BY MONTH  /  LAST 12 MONTHS',11,'label muted'),line(38,85,923)]
    st=statistics(days)
    if not st:
        s += [T(50,168,'Your real contribution statistics will appear here.',23,'serif muted'),
              T(50,202,'This preview uses no invented counts.',13,'muted')]
    else:
        today=date.today();months=[]
        for i in range(11,-1,-1):
            y=today.year;m=today.month-i
            while m<=0:y-=1;m+=12
            months.append(f'{y}-{m:02d}')
        vals=[st['months'].get(m,0) for m in months]
        peak=max(max(vals),1);best=max(range(12),key=lambda idx:vals[idx])
        for i,(m,n) in enumerate(zip(months,vals)):
            bh=max(2,round(n/peak*106));x=60+i*74;y=226-bh
            c=BLUE if i==best else '#B9B5AB'
            s.append(f'<rect x="{x}" y="{y}" width="35" height="{bh}" rx="4" fill="{c}" class="bar" style="--d:{1.25+i*.058:.3f}s"/>')
            if i==best and n:s.append(T(x+17,y-9,n,14,'rise',BLUE,extra='text-anchor="middle" style="--d:2s"'))
            s.append(T(x+17,248,date(int(m[:4]),int(m[5:]),1).strftime('%b'),11,'muted',extra='text-anchor="middle"'))
        s.append(line(55,226,913))
        bestday=st['best'][0].strftime('%d %b %Y')
        s.append(T(40,287,f"{st['total']:,} CONTRIBUTIONS    {st['active']} ACTIVE DAYS    {st['streak']} DAY STREAK",13))
        s.append(T(916,287,f"BUSIEST: {bestday}  ·  {st['best'][1]}",11,'muted',extra='text-anchor="end"'))
    return svg(960,309,''.join(s),fonts)

def tile(fonts,title,color,subtitle,num,delay,repo):
    s=[f'<path d="M18 236 L294 14" stroke="#FFF" stroke-opacity=".19"/>',
       '<circle cx="258" cy="199" r="92" stroke="white" stroke-opacity=".2" fill="none"/>',
       '<circle cx="258" cy="199" r="54" stroke="white" stroke-opacity=".13" fill="none"/>',
       T(24,40,f'{num} / {repo}',11,'label',color='white'),
       T(22,134,title,54,'serif tileEnter',color='white',extra=f'style="fill:white;--d:{delay:.2f}s"'),
       T(24,171,subtitle,14,'rise',color='white',extra=f'style="fill:white;--d:{delay+.16:.2f}s"'),
       '<path d="M24 218 H281" stroke="white" stroke-opacity=".65"/>',
       T(24,240,'OPEN PROJECT',11,'label',color='white'),
       '<g class="arrow" stroke="white" stroke-width="2" fill="none"><path d="M255 233 L283 205 M265 205 H283 V223"/></g>']
    return svg(306,254,''.join(s),fonts,bg=color)

def repo(fonts,r,idx):
    slug,title,description,meta,detail,color=r
    d=2.32+.17*idx
    s=[f'<rect x="0" y="0" width="960" height="4" fill="{color}"/>',
       T(34,50,f'{idx+1:02}',24,'serif rise',color,extra=f'style="fill:{color};--d:{d:.2f}s"'),
       f'<path d="M85 23 V146" stroke="{BORDER}"/>',
       T(112,64,title,37,'serif rise',extra=f'style="--d:{d+.04:.2f}s"'),
       T(113,101,description,18,'rise',extra=f'style="--d:{d+.13:.2f}s"'),
       T(113,140,meta,11,'label muted'),
       f'<g stroke="{color}" stroke-width="2.5" fill="none" class="rise" style="--d:{d+.2:.2f}s"><path d="M 890 57 L 922 25 M 901 25 H 922 V 46"/></g>',
       T(923,139,detail,13,'muted',extra='text-anchor="end"')]
    return svg(960,169,''.join(s),fonts)

def refresh():
    token=os.getenv('GITHUB_TOKEN')
    if not token: raise RuntimeError('GITHUB_TOKEN required for --refresh')
    query='''query($login: String!) { user(login:$login) { contributionsCollection {
       contributionCalendar { totalContributions weeks { contributionDays {date contributionCount} } }
    } } }'''
    data=json.dumps({'query':query,'variables':{'login':USERNAME}}).encode()
    request=Request('https://api.github.com/graphql',data=data,headers={
        'Authorization':f'Bearer {token}','Content-Type':'application/json','User-Agent':'profile-cards/1.0'})
    with urlopen(request,timeout=30) as response:payload=json.load(response)
    if payload.get('errors'):raise RuntimeError(f"GitHub GraphQL: {payload['errors']}")
    calendar=payload['data']['user']['contributionsCollection']['contributionCalendar']
    days=[{'date':day['date'],'count':int(day['contributionCount'])}
          for week in calendar['weeks'] for day in week['contributionDays']]
    DATA_FILE.parent.mkdir(parents=True,exist_ok=True)
    DATA_FILE.write_text(json.dumps({'username':USERNAME,'source':'github_graphql',
       'refreshed_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
       'total':calendar['totalContributions'],'days':days},indent=2)+'\n')
    print(f'Fetched {len(days)} real contribution days')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--refresh',action='store_true',help='Update JSON from authenticated GitHub GraphQL')
    args=parser.parse_args()
    if args.refresh:refresh()
    days=activity_data()
    fonts=font_faces()
    CARDS.mkdir(parents=True,exist_ok=True)
    content={
      'hero.svg':hero(fonts), 'contributions.svg':graph(fonts,days), 'activity.svg':monthly(fonts,days),
      'build.svg':tile(fonts,'BUILD',BLUE,'Useful tools. Thoughtful systems.','01',1.67,'TIMORA'),
      'play.svg':tile(fonts,'PLAY',RED,'Side quests. Digital worlds.','02',1.81,'GLITCHBOUND'),
      'learn.svg':tile(fonts,'LEARN',GOLD,'Curiosity turned into code.','03',1.95,'NOTEGEN AI'),
    }
    for i,r in enumerate(REPOS):content[f'repo-{r[0]}.svg']=repo(fonts,r,i)
    for filename,body in content.items():(CARDS/filename).write_text(body,encoding='utf-8')
    print(f'Rendered {len(content)} SVG cards ({"STATIC final frame" if STATIC else "animated"})')

if __name__ == '__main__':main()