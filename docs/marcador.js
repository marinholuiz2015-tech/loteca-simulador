(() => {
  const TESTE = window.__LOTECA_TESTE;
  if (!TESTE && (!/loteriasonline\.caixa\.gov\.br/.test(location.host) || !/loteca/i.test(location.href))) { alert('Abra a Loteca nas Loterias Online da Caixa (ja logado) e clique de novo no Marcador Loteca.'); return; }
  const ant = document.getElementById('lep-marcador'); if (ant) { ant.remove(); return; }
  const PAINEL = 'https://loteca-simulador.onrender.com';
  const KEY = 'lep_marcador';
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  let st = { vols: [], status: [], i: 0, ms: 120, rep: false };
  try { const s = JSON.parse(localStorage.getItem(KEY) || 'null'); if (s && s.vols) st = Object.assign(st, s); } catch (e) {}
  const salva = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} };
  let rodando = false, pausar = false;
  const norm = t => { t = String(t || '').toUpperCase().replace(/[^12X]/g, ''); return ['1', 'X', '2'].filter(k => t.indexOf(k) >= 0).map(k => k === 'X' ? 'x' : k).join('.'); };
  const parse = txt => String(txt || '').split(/\r?\n/).map(l => l.trim()).filter(Boolean).map(l => {
    let p = l.split(/[;\t,|]/).map(norm).filter(Boolean);
    if (p.length !== 14 && /^[12x]{14}$/i.test(l.replace(/\s/g, ''))) p = l.replace(/\s/g, '').split('').map(norm);
    if (p.length === 15) p = p.slice(1);
    return p.length === 14 ? p.join(';') : null;
  }).filter(Boolean);
  const combos = v => v.split(';').reduce((a, t) => a * t.split('.').length, 1);
  const custo = v => combos(v) * 2;
  const brl = n => 'R$ ' + n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const css = `#lep-marcador{position:fixed;top:12px;right:12px;bottom:12px;width:380px;z-index:2147483647;background:#fff;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.35);font:14px/1.4 system-ui,Segoe UI,Roboto,sans-serif;color:#1f2937;display:flex;flex-direction:column;overflow:hidden}
#lep-marcador *{box-sizing:border-box;font-family:inherit}
#lep-marcador .hd{background:linear-gradient(135deg,#0B6B50,#0E8F6B);color:#fff;padding:14px 16px;display:flex;align-items:center;gap:10px}
#lep-marcador .hd b{font-size:17px;flex:1}#lep-marcador .hd span{font-size:12px;opacity:.85}
#lep-marcador .x{background:rgba(255,255,255,.2);border:0;color:#fff;width:30px;height:30px;border-radius:8px;cursor:pointer;font-size:16px}
#lep-marcador .bd{padding:12px 16px;overflow:auto;flex:1;display:flex;flex-direction:column;gap:10px}
#lep-marcador .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
#lep-marcador button.b{border:1px solid #d1d5db;background:#fff;border-radius:10px;padding:8px 12px;cursor:pointer;font-weight:600;font-size:13px}
#lep-marcador button.b:hover{background:#f3f4f6}#lep-marcador button.p{background:#0B6B50;color:#fff;border-color:#0B6B50}#lep-marcador button.p:hover{background:#095a43}
#lep-marcador button.w{background:#F59E0B;color:#fff;border-color:#F59E0B}#lep-marcador button:disabled{opacity:.45;cursor:default}
#lep-marcador .kp{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
#lep-marcador .k{background:#f3f7f5;border-radius:12px;padding:8px;text-align:center}#lep-marcador .k b{display:block;font-size:22px;color:#0B6B50}#lep-marcador .k span{font-size:11px;color:#6b7280;text-transform:uppercase}
#lep-marcador .k.er b{color:#dc2626}
#lep-marcador .bar{height:8px;background:#e5e7eb;border-radius:9px;overflow:hidden}#lep-marcador .bar i{display:block;height:100%;background:#0E8F6B;width:0;transition:width .3s}
#lep-marcador label{font-size:13px;color:#374151;display:flex;align-items:center;gap:6px}
#lep-marcador input[type=number]{width:72px;padding:5px 8px;border:1px solid #d1d5db;border-radius:8px}
#lep-marcador .ls{flex:1;min-height:120px;overflow:auto;border:1px solid #e5e7eb;border-radius:12px;font:12px/1.5 ui-monospace,Consolas,monospace}
#lep-marcador .ls div{padding:4px 8px;border-bottom:1px solid #f3f4f6;display:flex;gap:8px;align-items:center}
#lep-marcador .ls div.at{background:#FEF3C7}#lep-marcador .ls div.ok{color:#047857}#lep-marcador .ls div.er{color:#dc2626;background:#FEF2F2}
#lep-marcador .ls em{font-style:normal;width:18px;text-align:center}#lep-marcador .ls s{text-decoration:none;color:#9ca3af;margin-left:auto}
#lep-marcador .msg{font-size:13px;border-radius:10px;padding:8px 10px;background:#ECFDF5;color:#065F46}#lep-marcador .msg.er{background:#FEF2F2;color:#991B1B}
#lep-marcador .ft{padding:12px 16px;border-top:1px solid #e5e7eb;display:flex;gap:8px}#lep-marcador .ft button{flex:1}
#lep-marcador textarea{width:100%;height:110px;border:1px solid #d1d5db;border-radius:10px;padding:8px;font:12px ui-monospace,Consolas,monospace}`;
  const el = document.createElement('div'); el.id = 'lep-marcador';
  el.innerHTML = `<style>${css}</style><div class="hd"><div style="flex:1"><b>Marcador Loteca</b><br><span>Loteca Elite Pro · marca e põe no carrinho · nunca paga</span></div><button class="x" data-a="min" title="Recolher">–</button><button class="x" data-a="fecha" title="Fechar">✕</button></div>
<div class="bd"><div class="row"><button class="b p" data-a="painel">Puxar do meu painel</button><button class="b" data-a="arq">Importar arquivo</button><button class="b" data-a="colar">Colar</button><input type="file" accept=".txt,.csv" hidden data-a="file"></div>
<div data-a="cola" hidden><textarea placeholder="Cole os volantes (formato SpeedLoto: 1;2.x;1;... um por linha)"></textarea><div class="row" style="margin-top:6px"><button class="b p" data-a="colaok">Carregar</button><button class="b" data-a="colanao">Cancelar</button></div></div>
<div class="kp"><div class="k"><b data-k="reg">0</b><span>A registrar</span></div><div class="k"><b data-k="ok">0</b><span>No carrinho</span></div><div class="k er"><b data-k="er">0</b><span>Com erro</span></div></div>
<div class="bar"><i></i></div><div class="row" style="justify-content:space-between;font-size:13px"><span data-k="custo"></span><span data-k="conc"></span></div>
<div class="row"><label>Intervalo <input type="number" min="40" max="2000" step="20" data-a="ms"> ms</label><label><input type="checkbox" data-a="rep"> Permitir repetidas</label></div>
<div data-a="msg"></div><div class="ls"></div></div>
<div class="ft"><button class="b p" data-a="enviar">ENVIAR</button><button class="b w" data-a="pausa" disabled>Pausar</button><button class="b" data-a="apagar">Apagar</button></div>`;
  document.body.appendChild(el);
  const q = s => el.querySelector(s);
  q('[data-a=ms]').value = st.ms; q('[data-a=rep]').checked = st.rep;
  const msg = (t, er) => { const m = q('[data-a=msg]'); m.className = t ? ('msg' + (er ? ' er' : '')) : ''; m.textContent = t || ''; };
  const conc = () => { const t = document.body.innerText.match(/Concurso\s*(?:n[ºo°]\s*)?(\d{3,5})/i); return t ? 'Concurso ' + t[1] : ''; };
  const desenha = () => {
    const ok = st.status.filter(s => s === 'ok').length, er = st.status.filter(s => s === 'er').length;
    q('[data-k=reg]').textContent = st.vols.length - ok; q('[data-k=ok]').textContent = ok; q('[data-k=er]').textContent = er;
    q('.bar i').style.width = (st.vols.length ? 100 * ok / st.vols.length : 0) + '%';
    const tot = st.vols.reduce((a, v) => a + custo(v), 0), noc = st.vols.reduce((a, v, n) => a + (st.status[n] === 'ok' ? custo(v) : 0), 0);
    q('[data-k=custo]').textContent = st.vols.length ? ('Total ' + brl(tot) + (noc ? ' · no carrinho ' + brl(noc) : '')) : 'Nenhum volante carregado';
    q('[data-k=conc]').textContent = conc();
    q('.ls').innerHTML = st.vols.map((v, n) => `<div class="${st.status[n] || ''}${n === st.i && rodando ? ' at' : ''}"><em>${st.status[n] === 'ok' ? '✓' : st.status[n] === 'er' ? '✕' : (n + 1)}</em>${v}<s>${brl(custo(v))}</s></div>`).join('');
    const a = q('.ls .at'); if (a) a.scrollIntoView({ block: 'nearest' });
    q('[data-a=enviar]').disabled = rodando || !st.vols.length; q('[data-a=pausa]').disabled = !rodando; q('[data-a=apagar]').disabled = rodando;
    q('[data-a=enviar]').textContent = st.status.some(s => s === 'ok' || s === 'er') && st.status.some(s => s !== 'ok') ? 'CONTINUAR' : 'ENVIAR';
  };
  const carrega = lista => {
    if (!lista.length) { msg('Não encontrei volantes válidos (cada linha precisa ter 14 jogos).', true); return; }
    if (!st.rep) { const vis = {}; lista = lista.filter(v => vis[v] ? false : (vis[v] = 1)); }
    const sem = lista.filter(v => combos(v) < 2).length;
    st.vols = lista; st.status = lista.map(() => ''); st.i = 0; salva(); desenha();
    msg(lista.length + ' volantes carregados.' + (sem ? ' Atenção: ' + sem + ' sem nenhum duplo (a Caixa exige pelo menos 1 duplo).' : ''), !!sem);
  };
  q('[data-a=arq]').onclick = () => q('[data-a=file]').click();
  q('[data-a=file]').onchange = e => { const f = e.target.files[0]; if (!f) return; const r = new FileReader(); r.onload = () => carrega(parse(r.result)); r.readAsText(f); e.target.value = ''; };
  q('[data-a=colar]').onclick = () => { q('[data-a=cola]').hidden = false; q('textarea').focus(); };
  q('[data-a=colanao]').onclick = () => { q('[data-a=cola]').hidden = true; };
  q('[data-a=colaok]').onclick = () => { carrega(parse(q('textarea').value)); q('[data-a=cola]').hidden = true; q('textarea').value = ''; };
  q('[data-a=painel]').onclick = () => {
    const w = window.open(PAINEL + '/painel/#enviar', 'lep_painel', 'width=560,height=720');
    if (!w) { msg('O navegador bloqueou a janela do painel. Libere pop-ups para este site e clique de novo.', true); return; }
    msg('Escolha na janela do painel quais volantes enviar.');
  };
  window.addEventListener('message', e => {
    if (e.origin !== PAINEL && !(TESTE && e.origin === location.origin)) return;
    if (!e.data || e.data.tipo !== 'loteca-volantes' || !Array.isArray(e.data.vols)) return;
    carrega(parse(e.data.vols.join('\n'))); if (e.data.nome) msg(st.vols.length + ' volantes de "' + e.data.nome + '" carregados.');
  });
  q('[data-a=ms]').onchange = e => { st.ms = Math.max(40, Number(e.target.value) || 120); salva(); };
  q('[data-a=rep]').onchange = e => { st.rep = e.target.checked; salva(); };
  q('[data-a=apagar]').onclick = () => { if (st.vols.length && !confirm('Apagar a lista do marcador?')) return; st.vols = []; st.status = []; st.i = 0; salva(); msg(''); desenha(); };
  q('[data-a=fecha]').onclick = () => { if (rodando && !confirm('A marcação está rodando. Fechar mesmo assim?')) return; pausar = true; el.remove(); };
  q('[data-a=min]').onclick = () => { const bd = q('.bd'), ft = q('.ft'); const h = bd.style.display === 'none'; bd.style.display = ft.style.display = h ? '' : 'none'; el.style.bottom = h ? '12px' : 'auto'; };
  q('[data-a=pausa]').onclick = () => { pausar = true; msg('Pausando depois deste volante…'); };
  const modal = () => [...document.querySelectorAll('.modal')].find(x => getComputedStyle(x).display !== 'none' && x.innerText.trim());
  const ordem = s => s.split('.').sort((a, b) => '1x2'.indexOf(a) - '1x2'.indexOf(b)).join('.');
  const marcaUm = async v => {
    const m = v.split(';');
    const lim = document.getElementById('limparvolante'); if (lim) lim.click(); await sleep(Math.max(250, st.ms * 2));
    const md0 = modal(); if (md0) return 'A Caixa mostrou: ' + md0.innerText.trim().slice(0, 160);
    const L = [...document.querySelectorAll('tr[ng-repeat*="partida in vm.partidas"]')];
    if (L.length !== 14) return 'Não encontrei os 14 jogos na página (o concurso está aberto?).';
    for (let i = 0; i < 14; i++) { const a = L[i].querySelectorAll('a.loteca_palpite'); for (const o of m[i].split('.')) { a[o === '1' ? 0 : (o === 'x' ? 1 : 2)].click(); await sleep(st.ms); } }
    await sleep(Math.max(250, st.ms * 2));
    const md = modal(); if (md) return 'A Caixa mostrou: ' + md.innerText.trim().slice(0, 160);
    const lido = L.map(tr => [...tr.querySelectorAll('a.loteca_palpite')].map((a, k) => a.classList.contains('loteca_palpite_selecionado') ? ['1', 'x', '2'][k] : '').filter(Boolean).join('.'));
    if (lido.join(';') !== m.map(ordem).join(';')) return 'A marcação na tela não conferiu com o volante.';
    const bt = document.getElementById('colocarnocarrinho'); if (!bt) return 'Não achei o botão "Colocar no carrinho".';
    bt.click(); await sleep(1500 + st.ms * 2);
    const md2 = modal();
    if (md2 && /erro|aten[cç]|n[aã]o foi|inv[aá]lid|limite|indispon/i.test(md2.innerText)) return 'A Caixa mostrou: ' + md2.innerText.trim().slice(0, 160);
    if (md2) { const f = md2.querySelector('#fecharModalAlerta,button'); if (f) f.click(); await sleep(400); }
    return null;
  };
  q('[data-a=enviar]').onclick = async () => {
    const pend = st.vols.map((v, n) => n).filter(n => st.status[n] !== 'ok');
    if (!pend.length) { msg('Todos já estão no carrinho.'); return; }
    const tot = pend.reduce((a, n) => a + custo(st.vols[n]), 0);
    if (!confirm(pend.length + ' volantes (' + brl(tot) + ') serão marcados e colocados no carrinho. O pagamento continua sendo seu. Começar?')) return;
    rodando = true; pausar = false; msg('Marcando… não mexa nesta aba até terminar.'); desenha();
    const m0 = modal(); if (m0) { const f0 = m0.querySelector('#fecharModalAlerta,button'); if (f0) f0.click(); await sleep(400); }
    for (const n of pend) {
      if (pausar) break;
      st.i = n; desenha();
      const erro = await marcaUm(st.vols[n]);
      if (erro) { st.status[n] = 'er'; salva(); rodando = false; desenha(); msg('Parei no volante ' + (n + 1) + ': ' + erro + ' Corrija e clique em CONTINUAR (ele refaz os que faltam).', true); return; }
      st.status[n] = 'ok'; salva(); document.title = 'Loteca ' + st.status.filter(s => s === 'ok').length + '/' + st.vols.length;
    }
    rodando = false; desenha();
    const ok = st.status.filter(s => s === 'ok').length;
    msg(pausar ? ('Pausado. ' + ok + ' de ' + st.vols.length + ' no carrinho. Clique em CONTINUAR quando quiser.') : ('Pronto: ' + ok + ' volantes no carrinho. Confira o carrinho e faça o pagamento você mesmo.'));
  };
  desenha();
  if (st.vols.length && st.status.some(s => s !== 'ok')) msg('Lista anterior recuperada: ' + st.status.filter(s => s === 'ok').length + ' de ' + st.vols.length + ' já estavam no carrinho.');
})();
