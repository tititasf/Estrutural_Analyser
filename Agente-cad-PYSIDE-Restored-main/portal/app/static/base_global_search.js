/* Owner-only knowledge search. Render source text as text, never as HTML. */
(function () {
  "use strict";
  var form = document.getElementById("bg-kb-form");
  var input = document.getElementById("bg-kb-q");
  var output = document.getElementById("bg-kb-resultado");
  if (!form || !input || !output) return;

  function node(tag, value) {
    var element = document.createElement(tag);
    element.textContent = value;
    return element;
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    output.replaceChildren(node("p", "Buscando…"));
    fetch("/app/base-global/buscar?q=" + encodeURIComponent(input.value), { credentials: "same-origin" })
      .then(function (response) {
        if (!response.ok) throw new Error("Busca indisponível (" + response.status + ")");
        return response.json();
      })
      .then(function (data) {
        output.replaceChildren();
        if (!data.resultados.length) {
          output.appendChild(node("p", "Nenhuma fonte encontrada."));
          return;
        }
        var list = document.createElement("ol");
        data.resultados.forEach(function (item) {
          var li = document.createElement("li");
          li.appendChild(node("strong", item.titulo || item.path));
          li.appendChild(node("p", item.path + (item.secao ? " § " + item.secao : "") + " · " + item.status));
          li.appendChild(node("p", item.trecho));
          list.appendChild(li);
        });
        output.appendChild(list);
      })
      .catch(function (error) { output.replaceChildren(node("p", error.message)); });
  });
})();
