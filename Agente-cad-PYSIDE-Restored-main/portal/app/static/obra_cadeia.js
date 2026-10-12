(function () {
  'use strict';
  var root = document.getElementById('obra-cadeia');
  if (!root) return;
  var obra = root.dataset.obra, btn = document.getElementById('btn-cadeia-completa');
  var options = document.getElementById('cadeia-opcoes'), output = document.getElementById('cadeia-resultado');
  var key = 'cad-cadeia-' + obra, timer, jobId, running = false, floorReady = false, last = {};
  var floorSelect = options.querySelector('[name="pavimento"]');
  var refresh = document.getElementById('cadeia-atualizar-pavimentos');
  function busy(value) { running = value; btn.disabled = value || !floorReady; options.disabled = value; }
  function save(value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {} }
  function show(text) { output.textContent = text; }
  function selected() {
    var values = {};
    options.querySelectorAll('select').forEach(function (el) { values[el.name] = el.value; });
    if (values.pavimento === '') values.pavimento = null;
    return values;
  }
  function loadFloors(preferred) {
    floorReady = false; floorSelect.disabled = true; refresh.disabled = true; busy(running);
    fetch('/obras/' + encodeURIComponent(obra) + '/cadeia-completa/pavimentos', {cache:'no-store'})
      .then(function (r) { if (!r.ok) throw new Error('Não foi possível carregar os pavimentos. Use Atualizar pavimentos.'); return r.json(); })
      .then(function (data) {
        floorSelect.replaceChildren();
        (data.pavimentos || []).forEach(function (pav) { floorSelect.add(new Option(pav, pav)); });
        floorReady = floorSelect.options.length > 0;
        if (floorReady) {
          floorSelect.add(new Option('Todos os pavimentos', ''));
          if (preferred === null) floorSelect.value = '';
          else if (preferred !== undefined) {
            floorSelect.value = preferred;
            if (floorSelect.selectedIndex < 0) {
              floorReady = false;
              show('O pavimento salvo não está disponível. Escolha um pavimento da lista atual.');
            }
          }
        } else {
          floorSelect.add(new Option('Nenhum pavimento com torre limpa', ''));
          if (!running) show('Conclua Triagem + Recortes e atualize os pavimentos para iniciar.');
        }
        floorSelect.disabled = !(data.pavimentos || []).length;
      }).catch(function (error) { if (!running) show(error.message); })
      .finally(function () { refresh.disabled = false; busy(running); });
  }
  floorSelect.addEventListener('change', function () {
    floorReady = floorSelect.selectedIndex >= 0 && !floorSelect.disabled;
    busy(running); if (!running) save({options:selected()});
  });
  refresh.addEventListener('click', function () { loadFloors(floorReady ? selected().pavimento : undefined); });
  function check() {
    fetch('/jobs/' + encodeURIComponent(jobId), {cache:'no-store'}).then(function (r) {
      if (!r.ok) throw new Error('Não foi possível consultar o processamento.');
      return r.json();
    }).then(function (job) {
      var c = job.cadeia || {}, count = c.concluidos || 0;
      var detail = c.pavimento ? c.pavimento + ' · ' + c.etapa + ' · ' + count + '/' + c.total + ' etapas concluídas' : 'Aguardando na fila';
      if (job.estado === 'done') {
        show(c.parcial ? '⚠ Processamento concluído com pendências por item. Os itens válidos foram publicados. ' + (c.pendencias || []).map(function (p) { return p.pavimento + ' · ' + p.etapa + ' · ' + (p.item_id || p.detalhe || '') + ': ' + (p.message || 'consulte o log'); }).join(' | ') : '✓ Processamento completo: pré-processamento, fichas SA, N3 e N5 de todas as classes publicados. ' + count + '/' + c.total + ' etapas concluídas.');
        busy(false); save({options:selected()});
        if (window.atualizaAposJob) window.atualizaAposJob();
        return;
      }
      if (['error','cancelled','paused'].indexOf(job.estado) >= 0) {
        show(detail + ' · ' + (job.erro_msg || 'Processamento interrompido.')); busy(false); save({options:selected()}); return;
      }
      var elapsed = job.progresso && job.progresso.decorrido_s;
      show(detail + (elapsed ? ' · ' + Math.floor(elapsed / 60) + ' min decorridos' : '')); timer = setTimeout(check, 3000);
    }).catch(function () { show('Reconectando ao acompanhamento; a execução continua no servidor.'); timer = setTimeout(check, 5000); });
  }
  btn.addEventListener('click', function () {
    if (timer) clearTimeout(timer);
    var values = selected();
    busy(true); show('Preparando a cadeia de ' + (values.pavimento || 'todos os pavimentos') + '…');
    fetch('/obras/' + encodeURIComponent(obra) + '/cadeia-completa', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(values)
    }).then(function (r) { return r.json().then(function (data) {
      if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível iniciar o processamento.');
      return data;
    }); }).then(function (data) {
      jobId = data.job_id; save({job:jobId, options:values}); check();
    }).catch(function (error) { show(error.message); busy(false); });
  });
  try {
    last = JSON.parse(localStorage.getItem(key) || '{}') || {};
    if (last.options) options.querySelectorAll('select').forEach(function (el) { if (el !== floorSelect && last.options[el.name]) el.value = last.options[el.name]; });
    if (last.job) { jobId = last.job; busy(true); check(); }
  } catch (_) {}
  loadFloors(last.options ? last.options.pavimento : undefined);
})();
