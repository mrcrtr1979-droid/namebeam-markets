import re,os,glob,sys
if not any('Perplexity cited' in open(f,encoding='utf-8').read() for f in glob.glob('record/*/index.html')): sys.exit('nothing to strip')
SRC='.'
OUT='.'
MARK='<p>Cited sources for Perplexity answers are held in the private record (2026-11-08).</p>'
os.chdir(SRC)
recs=[f for f in sorted(glob.glob('record/*/index.html')) if 'Perplexity cited' in open(f,encoding='utf-8').read()]
assert len(recs)==26
mk=['market_atlanta.html','market_phoenix.html','market_dallas.html']
def rd(f): return open(f,encoding='utf-8',newline='').read()
def wr(f,s):
    p=os.path.join(OUT,f); os.makedirs(os.path.dirname(p),exist_ok=True)
    open(p,'w',encoding='utf-8',newline='').write(s)
DROP_H={'its own site cited (days)','own pages Perplexity cited (days, last date)'}
cellre=re.compile(r'<t([hd])(?:\s[^>]*)?>.*?</t\1>',re.S)
def fix_table(m):
    t=m.group(0)
    ths=re.findall(r'<th(?:\s[^>]*)?>(.*?)</th>',re.search(r'<thead>.*?</thead>',t,re.S).group(0),re.S)
    if not DROP_H & set(ths): return t
    drop={i for i,h in enumerate(ths) if h in DROP_H}
    def row(r):
        cells=[c for c in cellre.finditer(r.group(1))]
        assert len(cells)==len(ths),(len(cells),len(ths))
        inner=r.group(1); out=''; pos=0
        for i,c in enumerate(cells):
            out+=inner[pos:c.start()]
            if i not in drop: out+=c.group(0)
            pos=c.end()
        out+=inner[pos:]
        # remove empty gap artefacts: none expected (cells adjacent)
        return '<tr>'+out+'</tr>'
    return re.sub(r'<tr>(.*?)</tr>',row,t,flags=re.S)
blockre=re.compile(r'<h3>Pages Perplexity cited on the most days in this market</h3>\n(?P<mid>.*?)\n<p class="pv-note">Source: the sources_cited list[^\n]*</p>\n(?:<p class="pv-note">Excluded \(not a single business\)[^\n]*</p>\n)?',re.S)
mids=set()
def blk(m):
    mids.add(m.group('mid')[:12]); assert '<h2' not in m.group('mid') and '<h3' not in m.group('mid')
    return MARK+'\n'
def do_receipt(f):
    s=rd(f)
    s=re.sub(r'<table>\s*<thead>.*?</table>',fix_table,s,flags=re.S) if False else re.sub(r'<table><thead>.*?</tbody></table>',fix_table,s,flags=re.S)
    s,n=blockre.subn(blk,s)
    assert n==s.count(MARK)>=1,(f,n)
    s,k=re.subn(r'<p class="pv-note">How to read it:[^\n]*</p>\n','',s); assert k==n,(f,k,n)
    return s
for f in recs+mk: wr(f,do_receipt(f))
print('mids',mids)
# sources
s=rd('sources/index.html')
a=s.index('<body><main>')+len('<body><main>'); b=s.index('<footer>')
s=s[:a]+'\n<h1>Sources</h1><p>This page is under review and its figures are held in the private record (2026-11-08).</p>\n'+s[b:]
s,n=re.subn(r'<meta name="description" content="Which domains Perplexity cited[^>]*>\n','<meta name="robots" content="noindex">\n',s); assert n==1
wr('sources/index.html',s)
# report
f='report/october-2026/index.html'; s=rd(f)
def cut(s,old,new=''):
    assert s.count(old)==1,old[:60]; return s.replace(old,new)
s=cut(s,'<li>Perplexity cited expertise.com on 248 of 642 cell-days with cited sources (38.6%) and yelp.com on 214 of 642 (33.3%), 2026-09-01 to 2026-09-26.</li>','')
# keep numbering 4,5 in the top list
s=cut(s,'<li>The engines rarely named the same businesses:','<li value="4">The engines rarely named the same businesses:')
i=s.index('<section id="f3">'); j=s.index('</section>',i)+len('</section>')
s=s[:i]+s[j:]
s=cut(s,' Perplexity collection changed in the files dated 2026-09-27, so the Perplexity cited-domain figures in finding 3 use 2026-09-01 to 2026-09-26. Perplexity figures in findings 1 and 4 and the listing comparison were computed through 2026-09-27 and have not been recomputed for the 2026-09-26 cut.','')
s=cut(s,' Perplexity changed its collection method in the files dated 2026-09-27; see Limits for which figures use 2026-09-26 as the last Perplexity day.',' Perplexity changed its collection method in the files dated 2026-09-27.')
wr(f,s)

# round 2: samples
for f in ['samples/wave2/temso.html','samples/wave2/cloro.html']:
    s=rd(f)
    s,a=re.subn(r'<tr><td>perplexity / sources_cited</td>.*?</tr>\n?','',s,flags=re.S)
    s,b=re.subn(r'<li>perplexity / sources_cited:.*?</li>\n?','',s,flags=re.S)
    print(f,'rows removed',a,'li removed',b,'left',s.count('sources_cited'))
    assert s.count('sources_cited')==0
    wr(f,s)
