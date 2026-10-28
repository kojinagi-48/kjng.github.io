#!/usr/bin/env python3
"""Aggregate public RSS headlines into a static, source-attributed JSON feed."""
import calendar, datetime as dt, email.utils, hashlib, html, json, pathlib, re, urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'news.json'
FEEDS = [
    ('IGN', 'Games', 'https://feeds.feedburner.com/ign/games-all'),
    ('GameSpot', 'Games', 'https://www.gamespot.com/feeds/game-news/'),
    ('PC Gamer', 'Games', 'https://www.pcgamer.com/rss/'),
    ('Anime News Network', 'Anime', 'https://www.animenewsnetwork.com/news/rss.xml?ann-edition=us'),
    ('Anime News Network', 'Manga', 'https://www.animenewsnetwork.com/news/rss.xml?ann-edition=us'),
    ('ComicBook.com', 'Comics', 'https://comicbook.com/feed/'),
    ('IGN', 'Film', 'https://feeds.feedburner.com/ign/movies-articles'),
    ('GameSpot', 'Film', 'https://www.gamespot.com/feeds/entertainment-news/'),
    ('ComicBook.com', 'Film', 'https://comicbook.com/feed/'),
]
MANGA = re.compile(r'\b(manga|mangaka|one[- ]shot|serialization|shonen jump|weekly shonen|graphic novel)\b',re.I)
ANIME = re.compile(r'\b(anime|animation|animator|anime film|crunchyroll|studio ghibli)\b',re.I)
COMICS = re.compile(r'\b(comic|marvel|dc comics|superman|batman|x-men|spider-man|graphic novel)\b',re.I)
FILM = re.compile(r'\b(film|movie|cinema|box office|trailer|director|hollywood|theater|netflix)\b',re.I)
class Plain(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self,data): self.parts.append(data)
def strip(s):
    p=Plain()
    try:p.feed(html.unescape(s or ''))
    except Exception:return ''
    return re.sub(r'\s+',' ',' '.join(p.parts)).strip()
def first(el,names):
    for name in names:
        v=el.findtext(name)
        if v and v.strip():return v.strip()
    return ''
def dateparse(s):
    if not s:return None
    try:d=email.utils.parsedate_to_datetime(s)
    except Exception:
        try:d=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
        except Exception:return None
    if not d.tzinfo:d=d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)
def image_of(el,description):
    # Image links come from publishers' own RSS media or enclosure metadata.
    for node in el.iter():
        name=node.tag.rsplit('}',1)[-1].lower()
        if name in ('thumbnail','content','enclosure'):
            u=node.attrib.get('url','')
            if u.startswith('https://') and (name!='enclosure' or node.attrib.get('type','').startswith('image/')):return u
    m=re.search(r'<img[^>]+src=["\'](https://[^"\']+)',description or '',re.I)
    return html.unescape(m.group(1)) if m else ''
def clean_url(url):
    try:
        p=urlparse(url)
        if p.scheme not in ('https','http') or not p.netloc:return ''
        q=[(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid')]
        return urlunparse((p.scheme,p.netloc,p.path,p.params,urlencode(q),''))
    except Exception:return ''
def categorize(source,cat,title,summary):
    s=title+' '+summary
    if source=='Anime News Network':
        return 'Manga' if MANGA.search(s) and not ANIME.search(title) else 'Anime'
    if source=='ComicBook.com':
        if MANGA.search(title):return 'Manga'
        if ANIME.search(title):return 'Anime'
        if FILM.search(title):return 'Film'
        if COMICS.search(s):return 'Comics'
        return 'Comics'
    if cat=='Film' and not (FILM.search(s) or ANIME.search(s)):return None
    return cat
def gather(source,cat,url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; PulseRSS/1.0; public feed aggregation)','Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.8'})
    with urllib.request.urlopen(req,timeout=24) as response: raw=response.read(3_000_000)
    root=ET.fromstring(raw)
    entries=root.findall('.//item')
    if not entries:entries=root.findall('{http://www.w3.org/2005/Atom}entry')
    out=[]
    for node in entries[:65]:
        atom='{http://www.w3.org/2005/Atom}'
        title=strip(first(node,['title',atom+'title']))
        url=first(node,['link'])
        if not url:
            lk=node.find(atom+'link')
            url=lk.attrib.get('href','') if lk is not None else ''
        url=clean_url(url)
        if not title or not url:continue
        raw_description=first(node,['description',atom+'summary','{http://purl.org/rss/1.0/modules/content/}encoded'])
        summary=strip(raw_description)[:250]
        pub=dateparse(first(node,['pubDate',atom+'published',atom+'updated','{http://purl.org/dc/elements/1.1/}date']))
        if pub and pub > dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=1):continue
        actual=categorize(source,cat,title,summary)
        if not actual:continue
        out.append({'title':title[:230],'url':url,'source':source,'category':actual,'summary':summary,'image':image_of(node,raw_description),'published':pub.isoformat().replace('+00:00','Z') if pub else ''})
    return out
def main():
    old=[]
    try:old=json.loads(OUT.read_text(encoding='utf-8')).get('articles',[])
    except Exception:pass
    combined=[]
    for source,cat,url in FEEDS:
        try:
            items=gather(source,cat,url)
            print(f'{source} / {cat}: {len(items)} stories')
            combined+=items
        except Exception as exc:print(f'Warning: {source} / {cat}: {exc}')
    # Retain recent articles when a publisher temporarily blocks or times out.
    now=dt.datetime.now(dt.timezone.utc)
    combined+=old
    dedup={}
    for item in combined:
        key=clean_url(item.get('url',''))
        if not key or key in dedup:continue
        pub=dateparse(item.get('published',''))
        if pub and pub<now-dt.timedelta(days=30):continue
        item['url']=key
        dedup[key]=item
    result=sorted(dedup.values(),key=lambda a:a.get('published',''),reverse=True)[:240]
    if not result:raise RuntimeError('No articles fetched; preserving previous dataset')
    payload={'updated':now.isoformat().replace('+00:00','Z'),'article_count':len(result),'articles':result}
    OUT.parent.mkdir(exist_ok=True,parents=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Wrote {len(result)} articles')
if __name__=='__main__':main()
