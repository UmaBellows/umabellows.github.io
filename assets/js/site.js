// Uma Bellows — shared site behavior (replaces the vendored AOS/PureCounter/Isotope stack)
(function () {
  "use strict";

  // Gate .reveal's hidden state behind JS actually running — see site.css:
  // without this class, .reveal elements stay visible if the script never loads.
  document.body.classList.add("js-ready");

  // Mobile nav toggle
  var toggle = document.querySelector(".nav-toggle");
  var mobileNav = document.querySelector(".mobile-nav");
  if (toggle && mobileNav) {
    toggle.addEventListener("click", function () {
      var open = mobileNav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Scroll reveal
  var revealEls = document.querySelectorAll(".reveal");
  if (revealEls.length) {
    if (reduceMotion || !("IntersectionObserver" in window)) {
      revealEls.forEach(function (el) { el.classList.add("in"); });
    } else {
      var io = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              entry.target.classList.add("in");
              io.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.15 }
      );
      revealEls.forEach(function (el) { io.observe(el); });
    }
  }

  // Stat counters — animate once when in view
  var counters = document.querySelectorAll("[data-count-to]");
  if (counters.length) {
    var animateCounter = function (el) {
      var target = parseInt(el.getAttribute("data-count-to"), 10) || 0;
      if (reduceMotion) { el.textContent = target; return; }
      var start = 0;
      var duration = 900;
      var startTime = null;
      function step(ts) {
        if (!startTime) startTime = ts;
        var progress = Math.min((ts - startTime) / duration, 1);
        el.textContent = Math.floor(start + (target - start) * progress);
        if (progress < 1) requestAnimationFrame(step);
        else el.textContent = target;
      }
      requestAnimationFrame(step);
    };
    if ("IntersectionObserver" in window) {
      var cio = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              animateCounter(entry.target);
              cio.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.4 }
      );
      counters.forEach(function (el) { cio.observe(el); });
    } else {
      counters.forEach(animateCounter);
    }
  }

  // Hero image slider — dependency-free, pauses on hover/focus, respects reduced-motion
  var heroSlider = document.querySelector("[data-hero-slider]");
  if (heroSlider) {
    var slides = Array.prototype.slice.call(heroSlider.querySelectorAll(".hero-slide"));
    var dotsWrap = heroSlider.querySelector(".hero-slider-dots");
    var prevBtn = heroSlider.querySelector(".hero-slider-arrow.prev");
    var nextBtn = heroSlider.querySelector(".hero-slider-arrow.next");
    var current = slides.findIndex(function (s) { return s.classList.contains("is-active"); });
    if (current < 0) current = 0;
    var timer = null;
    var interval = parseInt(heroSlider.getAttribute("data-interval"), 10) || 5000;

    var dots = slides.map(function (_, i) {
      var b = document.createElement("button");
      b.type = "button";
      b.setAttribute("aria-label", "Go to image " + (i + 1));
      if (i === current) b.classList.add("is-active");
      b.addEventListener("click", function () { goTo(i); restart(); });
      dotsWrap.appendChild(b);
      return b;
    });

    function show(i) {
      slides[current].classList.remove("is-active");
      dots[current].classList.remove("is-active");
      current = (i + slides.length) % slides.length;
      slides[current].classList.add("is-active");
      dots[current].classList.add("is-active");
    }
    function goTo(i) { show(i); }
    function next() { show(current + 1); }
    function prev() { show(current - 1); }
    function stop() { if (timer) { clearInterval(timer); timer = null; } }
    function start() { if (!reduceMotion) { stop(); timer = setInterval(next, interval); } }
    function restart() { stop(); start(); }

    if (prevBtn) prevBtn.addEventListener("click", function () { prev(); restart(); });
    if (nextBtn) nextBtn.addEventListener("click", function () { next(); restart(); });
    heroSlider.addEventListener("mouseenter", stop);
    heroSlider.addEventListener("mouseleave", start);
    heroSlider.addEventListener("focusin", stop);
    heroSlider.addEventListener("focusout", start);

    start();
  }
})();
