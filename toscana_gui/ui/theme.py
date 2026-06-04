from __future__ import annotations

import panel as pn

from toscana_gui.paths import REPO_ROOT

APP_TITLE = "ToScaNA GUI"
LOGO_PATH = REPO_ROOT / "assets" / "institut-laue-langevin.png"
APP_CSS_PATH = REPO_ROOT / "assets" / "toscana.css"

SCROLL_PRESERVE_JS = r"""
(() => {
  if (window.__toscana_scroll_fix_installed) return;
  window.__toscana_scroll_fix_installed = true;

  let lastScrollX = window.scrollX || 0;
  let lastScrollY = window.scrollY || 0;
  let lastInteractionAt = 0;
  let lockUntil = 0;
  let wrappedScrollApis = false;

  const scrollToMethodAnchor = () => {
    const anchor = document.getElementById("toscana-bg-method-anchor");
    if (!anchor) return false;
    const rect = anchor.getBoundingClientRect();
    if (!rect) return false;
    const top = (window.scrollY || 0) + rect.top;
    const target = Math.max(0, top - 90);
    window.scrollTo(lastScrollX, target);
    return true;
  };

  const rememberScroll = () => {
    lastScrollX = window.scrollX || 0;
    lastScrollY = window.scrollY || 0;
    lastInteractionAt = Date.now();
    lockUntil = lastInteractionAt + 1200;
  };

  const shouldBlockScrollToTop = (targetY) => {
    const now = Date.now();
    if (now > lockUntil) return false;
    if (lastScrollY <= 100) return false;
    if (targetY == null) return false;
    return Number(targetY) <= 30;
  };

  const wrapScrollApisOnce = () => {
    if (wrappedScrollApis) return;
    wrappedScrollApis = true;

    try {
      const originalScrollTo = window.scrollTo ? window.scrollTo.bind(window) : null;
      if (originalScrollTo) {
        window.scrollTo = function(x, y) {
          if (shouldBlockScrollToTop(y)) {
            return originalScrollTo(lastScrollX, lastScrollY);
          }
          return originalScrollTo(x, y);
        };
      }
    } catch (e) {}

    try {
      const originalIntoView = Element.prototype.scrollIntoView;
      if (originalIntoView) {
        Element.prototype.scrollIntoView = function() {
          if (shouldBlockScrollToTop(0)) return;
          return originalIntoView.apply(this, arguments);
        };
      }
    } catch (e) {}
  };

  const restoreIfJumped = () => {
    const now = Date.now();
    if (now - lastInteractionAt > 12000) return;

    const currentY = window.scrollY || 0;
    if (lastScrollY <= 100) return;
    if (currentY >= 30) return;

    // If the page height collapsed (browser clamps scrollY to 0), at least keep
    // the "Background Subtraction Method" area visible.
    if (currentY <= 2) {
      if (scrollToMethodAnchor()) return;
    }

    const maxScrollY = Math.max(
      0,
      (document.documentElement && document.documentElement.scrollHeight ? document.documentElement.scrollHeight : 0) - (window.innerHeight || 0)
    );
    if (lastScrollY > maxScrollY + 40) return;

    window.scrollTo(lastScrollX, lastScrollY);
  };

  const scheduleRestore = () => {
    setTimeout(restoreIfJumped, 0);
    setTimeout(restoreIfJumped, 60);
    setTimeout(restoreIfJumped, 220);
    setTimeout(restoreIfJumped, 600);
    setTimeout(restoreIfJumped, 1200);
    setTimeout(restoreIfJumped, 1800);
    setTimeout(restoreIfJumped, 2600);
    setTimeout(restoreIfJumped, 3600);
    setTimeout(restoreIfJumped, 5000);
    setTimeout(restoreIfJumped, 8000);
    setTimeout(restoreIfJumped, 11000);
  };

  const normalizeButtons = () => {
    const buttons = document.querySelectorAll(".bk-root button, .pn-wrapper button");
    for (const btn of buttons) {
      const t = (btn.getAttribute("type") || "").toLowerCase();
      if (!t || t === "submit") btn.setAttribute("type", "button");
    }
  };

  document.addEventListener("pointerdown", rememberScroll, true);
  document.addEventListener("touchstart", rememberScroll, true);
  document.addEventListener("wheel", rememberScroll, {capture: true, passive: true});
  window.addEventListener("scroll", () => {
    lastScrollX = window.scrollX || 0;
    lastScrollY = window.scrollY || 0;
  }, {passive: true});

  // Guard against accidental form submits inside Panel/Bokeh templates.
  document.addEventListener("click", (ev) => {
    wrapScrollApisOnce();
    rememberScroll();
    const btn = ev.target && ev.target.closest ? ev.target.closest("button") : null;
    if (btn) {
      const t = (btn.getAttribute("type") || "").toLowerCase();
      const inPanelRoot = btn.closest && (btn.closest(".bk-root") || btn.closest(".pn-wrapper"));
      if (inPanelRoot && (!t || t === "submit")) ev.preventDefault();
    }
    scheduleRestore();
  }, true);

  document.addEventListener("change", () => {
    wrapScrollApisOnce();
    rememberScroll();
    scheduleRestore();
  }, true);

  document.addEventListener("submit", (ev) => {
    const root = ev.target && ev.target.closest ? (ev.target.closest(".bk-root") || ev.target.closest(".pn-wrapper")) : null;
    if (root) {
      ev.preventDefault();
      scheduleRestore();
    }
  }, true);

  normalizeButtons();
  const observer = new MutationObserver(() => {
    normalizeButtons();
    scheduleRestore();
  });
  observer.observe(document.documentElement, {subtree: true, childList: true});
})();
"""

def _install_scroll_preserver() -> None:
    try:
        pn.state.execute(SCROLL_PRESERVE_JS)
    except Exception:
        return


def configure_panel() -> None:
    css_text = APP_CSS_PATH.read_text(encoding="utf-8")
    pn.extension("plotly", "mathjax", notifications=True)
    if css_text not in pn.config.raw_css:
        pn.config.raw_css.append(css_text)
    try:
        from panel.io.reload import watch

        watch(str(APP_CSS_PATH.resolve()))
    except Exception:
        pass
    if pn.state.notifications is not None:
        pn.state.notifications.position = "top-right"
        pn.state.notifications.max_notifications = 2
    pn.state.onload(_install_scroll_preserver)
