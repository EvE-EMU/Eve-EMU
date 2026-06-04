(function () {
    "use strict";

    var toastEl = null;
    var toastTimer = null;

    function ensureToast() {
        if (toastEl) {
            return toastEl;
        }
        toastEl = document.createElement("div");
        toastEl.className = "emu-copy-toast";
        toastEl.setAttribute("role", "status");
        toastEl.setAttribute("aria-live", "polite");
        document.body.appendChild(toastEl);
        return toastEl;
    }

    function showToast(message) {
        var el = ensureToast();
        el.textContent = message;
        el.classList.add("show");
        if (toastTimer) {
            window.clearTimeout(toastTimer);
        }
        toastTimer = window.setTimeout(function () {
            el.classList.remove("show");
        }, 1600);
    }

    function copyText(value) {
        if (!value) {
            return Promise.reject(new Error("empty"));
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(value);
        }
        var area = document.createElement("textarea");
        area.value = value;
        area.setAttribute("readonly", "");
        area.style.position = "absolute";
        area.style.left = "-9999px";
        document.body.appendChild(area);
        area.select();
        try {
            document.execCommand("copy");
            return Promise.resolve();
        } finally {
            document.body.removeChild(area);
        }
    }

    function markCopied(node) {
        node.classList.add("copied");
        window.setTimeout(function () {
            node.classList.remove("copied");
        }, 1200);
    }

    function activate(node) {
        var value = node.getAttribute("data-copy") || node.textContent.trim();
        copyText(value)
            .then(function () {
                markCopied(node);
                showToast(node.getAttribute("data-copy-label") || "Copied!");
            })
            .catch(function () {
                showToast("Copy failed");
            });
    }

    document.addEventListener("click", function (event) {
        var node = event.target.closest(".emu-copyable");
        if (!node) {
            return;
        }
        event.preventDefault();
        activate(node);
    });

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" && event.key !== " ") {
            return;
        }
        var node = event.target.closest(".emu-copyable");
        if (!node) {
            return;
        }
        event.preventDefault();
        activate(node);
    });
})();
