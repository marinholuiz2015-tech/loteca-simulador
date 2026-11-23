"""Gera o favorito (bookmarklet) Marcador Loteca a partir de docs/marcador.js e grava em docs/index.html."""
import json, urllib.parse, pathlib
raiz = pathlib.Path(__file__).resolve().parent.parent
code = (raiz / 'docs/marcador.js').read_text(encoding='utf-8').strip()
bm = 'javascript:' + urllib.parse.quote(code, safe="()[]{};,=+-*/!?:'.&|<>_~@$^ ")
p = raiz / 'docs/index.html'; s = p.read_text(encoding='utf-8')
a = s.index('var MARCADOR = "'); b = s.index('\n', a)
p.write_text(s[:a] + 'var MARCADOR = ' + json.dumps(bm) + ';' + s[b:], encoding='utf-8')
print('Marcador gerado:', len(bm), 'caracteres')
