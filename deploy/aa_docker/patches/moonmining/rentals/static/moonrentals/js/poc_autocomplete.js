/**
 * Alliance Auth user search for moon rental POC field.
 * Expects: #poc-search, #id_main_poc_id, #id_main_poc_label, #poc-suggestions
 */
(function () {
  const searchInput = document.getElementById("poc-search");
  const hiddenId = document.getElementById("id_main_poc_id");
  const list = document.getElementById("poc-suggestions");
  if (!searchInput || !hiddenId || !list) {
    return;
  }

  const searchUrl = searchInput.dataset.searchUrl;
  let timer = null;

  function clearSuggestions() {
    list.innerHTML = "";
    list.classList.add("d-none");
  }

  function pick(user) {
    hiddenId.value = user.id;
    searchInput.value = user.label;
    clearSuggestions();
  }

  function render(items) {
    list.innerHTML = "";
    if (!items.length) {
      list.classList.add("d-none");
      return;
    }
    items.forEach((user) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "list-group-item list-group-item-action";
      btn.textContent = user.label + (user.username ? ` (${user.username})` : "");
      btn.addEventListener("click", () => pick(user));
      list.appendChild(btn);
    });
    list.classList.remove("d-none");
  }

  searchInput.addEventListener("input", function () {
    const q = searchInput.value.trim();
    if (timer) {
      clearTimeout(timer);
    }
    if (q.length < 2) {
      clearSuggestions();
      return;
    }
    timer = setTimeout(function () {
      fetch(searchUrl + "?q=" + encodeURIComponent(q), {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      })
        .then((r) => r.json())
        .then((data) => render(data.results || []))
        .catch(() => clearSuggestions());
    }, 250);
  });

  document.addEventListener("click", function (e) {
    if (!list.contains(e.target) && e.target !== searchInput) {
      clearSuggestions();
    }
  });
})();
