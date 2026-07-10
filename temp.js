
      (function () {
        var jobId = {{ job_ativo|tojson }};
        var alvo = document.getElementById('job-estado');
        var mapa = {
          queued: 'Na fila — começa em breve.',
          running: 'Processando… isso costuma levar alguns minutos.',
          done: 'Concluído. Recarregando…',
          error: 'O processamento falhou nesta obra. O responsável foi notificado.'
        };
        function poll() {
          fetch('/jobs/' + jobId).then(function (r) { return r.json(); })
            .then(function (j) {
              alvo.textContent = mapa[j.estado] || j.estado;
              if (j.estado === 'done') { setTimeout(function () { location.reload(); }, 1200); }
              else if (j.estado === 'error') { /* para o polling */ }
              else { setTimeout(poll, 4000); }
            }).catch(function () { setTimeout(poll, 6000); });
        }
        poll();
      })();
    