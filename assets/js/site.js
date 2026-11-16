// Uma Bellows — shared site behavior (no libraries)
(function () {
  "use strict";

  var reduceMotion = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  // Mobile nav: toggle button, closes on Escape and after a link is followed
  var toggle = document.querySelector(".nav-toggle");
  var mobileNav = document.querySelector(".mobile-nav");
  if (toggle && mobileNav) {
    var setOpen = function (open) {
      mobileNav.classList.toggle("open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    };
    toggle.addEventListener("click", function () {
      setOpen(!mobileNav.classList.contains("open"));
    });
    mobileNav.addEventListener("click", function (e) {
      if (e.target.closest && e.target.closest("a")) setOpen(false);
    });
    document.addEventListener("keydown", function (e) {
      if ((e.key === "Escape" || e.key === "Esc") && mobileNav.classList.contains("open")) {
        setOpen(false);
        toggle.focus();
      }
    });
  }

  // Scroll reveal. .reveal content is only hidden (body.js-ready, see site.css)
  // once the observer is running, so a failure anywhere leaves it visible.
  // threshold 0 reveals an element as soon as any part of it is on screen,
  // however tall it is compared with the viewport.
  var revealEls = document.querySelectorAll(".reveal");
  if (revealEls.length && !reduceMotion && "IntersectionObserver" in window) {
    try {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            io.unobserve(entry.target);
          }
        });
      }, { threshold: 0, rootMargin: "0px 0px -10% 0px" });
      revealEls.forEach(function (el) { io.observe(el); });
      document.body.classList.add("js-ready");
    } catch (err) {
      document.body.classList.remove("js-ready");
    }
  }

  // Stat counters. The real number is in the HTML (what crawlers and no-JS
  // visitors see); with motion allowed it counts up once when scrolled into view.
  var counters = document.querySelectorAll("[data-count-to]");
  if (counters.length && !reduceMotion && "IntersectionObserver" in window) {
    var animateCounter = function (el) {
      var target = parseInt(el.getAttribute("data-count-to"), 10) || 0;
      var duration = 900, startTime = null;
      function step(ts) {
        if (startTime === null) startTime = ts;
        var progress = Math.min((ts - startTime) / duration, 1);
        el.textContent = progress < 1 ? String(Math.floor(target * progress)) : String(target);
        if (progress < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    };
    var cio = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          animateCounter(entry.target);
          cio.unobserve(entry.target);
        }
      });
    }, { threshold: 0.4 });
    counters.forEach(function (el) {
      el.textContent = "0";
      cio.observe(el);
    });
  }

  // Hero slider. Autoplays with a pause/play button (WCAG 2.2.2). Hovering
  // pauses it; keyboard focus inside it stops it until Play is pressed; it
  // never runs while the tab is hidden or when reduced motion is requested.
  var slider = document.querySelector("[data-hero-slider]");
  var slides = slider ? Array.prototype.slice.call(slider.querySelectorAll(".hero-slide")) : [];
  if (slides.length > 1) {
    var dotsWrap = slider.querySelector(".hero-slider-dots");
    var prevBtn = slider.querySelector(".hero-slider-arrow.prev");
    var nextBtn = slider.querySelector(".hero-slider-arrow.next");
    var interval = parseInt(slider.getAttribute("data-interval"), 10) || 5000;
    var current = Math.max(0, slides.findIndex(function (s) { return s.classList.contains("is-active"); }));
    var playing = !reduceMotion;
    var hovering = false;
    var timer = null;
    var playBtn = null;

    var canRun = function () { return playing && !hovering && !document.hidden; };
    var restartTimer = function () {
      if (timer) { clearInterval(timer); timer = null; }
      if (canRun()) timer = setInterval(function () { show(current + 1, true); }, interval);
    };
    var dots = slides.map(function (slide, i) {
      slide.setAttribute("role", "group");
      slide.setAttribute("aria-roledescription", "slide");
      slide.setAttribute("aria-label", (i + 1) + " of " + slides.length);
      if (!dotsWrap) return null;
      var b = document.createElement("button");
      b.type = "button";
      b.setAttribute("aria-label", "Go to image " + (i + 1));
      b.addEventListener("click", function () { show(i); });
      dotsWrap.appendChild(b);
      return b;
    });
    var render = function () {
      slides.forEach(function (s, i) {
        var on = i === current;
        s.classList.toggle("is-active", on);
        if (on) s.removeAttribute("aria-hidden"); else s.setAttribute("aria-hidden", "true");
        if (dots[i]) {
          dots[i].classList.toggle("is-active", on);
          if (on) dots[i].setAttribute("aria-current", "true"); else dots[i].removeAttribute("aria-current");
        }
      });
    };
    // auto = true for timer ticks; manual changes restart the interval (and
    // only resume autoplay when it is allowed to run).
    var show = function (i, auto) {
      current = (i + slides.length) % slides.length;
      render();
      if (!auto) restartTimer();
    };
    var syncPlayButton = function () {
      if (!playBtn) return;
      playBtn.setAttribute("aria-label", playing ? "Pause slideshow" : "Play slideshow");
      playBtn.textContent = playing ? "❚❚" : "▶︎";
    };

    if (!reduceMotion) {
      playBtn = document.createElement("button");
      playBtn.type = "button";
      playBtn.className = "hero-slider-toggle";
      playBtn.addEventListener("click", function () {
        playing = !playing;
        syncPlayButton();
        restartTimer();
      });
      slider.appendChild(playBtn);
    }
    if (prevBtn) prevBtn.addEventListener("click", function () { show(current - 1); });
    if (nextBtn) nextBtn.addEventListener("click", function () { show(current + 1); });
    slider.addEventListener("mouseenter", function () { hovering = true; restartTimer(); });
    slider.addEventListener("mouseleave", function () { hovering = false; restartTimer(); });
    slider.addEventListener("focusin", function (e) {
      // Keyboard focus stops the slideshow; a mouse click only pauses it (via hover).
      var keyboard = true;
      try { keyboard = e.target.matches(":focus-visible"); } catch (err) { /* older browsers */ }
      if (keyboard && playing) {
        playing = false;
        syncPlayButton();
        restartTimer();
      }
    });
    document.addEventListener("visibilitychange", restartTimer);

    render();
    syncPlayButton();
    restartTimer();
  }
})();
