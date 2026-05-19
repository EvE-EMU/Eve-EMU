(function () {
    "use strict";

    function debounce(fn, ms) {
        let timer;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), ms);
        };
    }

    function initSystemAutocomplete(root) {
        const input = root.querySelector("input");
        const menu = root.querySelector(".corp-orders-system-ac-menu");
        const url = root.dataset.searchUrl;
        if (!input || !menu || !url) {
            return;
        }

        let activeIndex = -1;
        let items = [];

        function hideMenu() {
            menu.classList.add("d-none");
            menu.innerHTML = "";
            activeIndex = -1;
            items = [];
        }

        function renderMenu(names) {
            items = names;
            menu.innerHTML = "";
            if (!names.length) {
                hideMenu();
                return;
            }
            names.forEach((name, idx) => {
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "list-group-item list-group-item-action";
                btn.textContent = name;
                btn.dataset.index = String(idx);
                btn.addEventListener("mousedown", (e) => {
                    e.preventDefault();
                    input.value = name;
                    hideMenu();
                });
                menu.appendChild(btn);
            });
            menu.classList.remove("d-none");
            activeIndex = -1;
        }

        function setActive(idx) {
            const buttons = menu.querySelectorAll(".list-group-item");
            buttons.forEach((el, i) => el.classList.toggle("active", i === idx));
            activeIndex = idx;
        }

        const fetchSystems = debounce(() => {
            const q = input.value.trim();
            const params = new URLSearchParams({ q });
            fetch(`${url}?${params.toString()}`, {
                headers: { Accept: "application/json" },
                credentials: "same-origin",
            })
                .then((r) => {
                    if (!r.ok) {
                        throw new Error("search failed");
                    }
                    return r.json();
                })
                .then((data) => renderMenu(data.systems || []))
                .catch(() => hideMenu());
        }, 180);

        input.addEventListener("focus", () => fetchSystems());
        input.addEventListener("input", () => fetchSystems());
        input.addEventListener("keydown", (e) => {
            if (menu.classList.contains("d-none") || !items.length) {
                return;
            }
            if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive(Math.min(activeIndex + 1, items.length - 1));
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive(Math.max(activeIndex - 1, 0));
            } else if (e.key === "Enter" && activeIndex >= 0) {
                e.preventDefault();
                input.value = items[activeIndex];
                hideMenu();
            } else if (e.key === "Escape") {
                hideMenu();
            }
        });

        document.addEventListener("click", (e) => {
            if (!root.contains(e.target)) {
                hideMenu();
            }
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll(".corp-orders-system-ac").forEach(initSystemAutocomplete);
    });
})();
