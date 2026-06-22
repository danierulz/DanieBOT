(function () {
  var STORAGE_KEY = 'outfitJazminesLogoPlayed';
  var FULL_MS = 2600;
  var HOVER_MS = 900;

  function resetLogoState(svg) {
    svg.classList.remove(
      'brand-logo--animate',
      'brand-logo--hover-replay',
      'brand-logo--done',
      'brand-logo--instant',
      'brand-logo--force-animate'
    );
  }

  function setFinalState(svg) {
    svg.classList.remove('brand-logo--animate', 'brand-logo--hover-replay', 'brand-logo--force-animate');
    svg.classList.add('brand-logo--done');
  }

  function playFullAnimation(svg) {
    resetLogoState(svg);
    void svg.offsetWidth;
    svg.classList.add('brand-logo--force-animate');
    window.setTimeout(function () {
      setFinalState(svg);
    }, FULL_MS);
  }

  function prefersReducedMotion() {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function initLogo(link) {
    var svg = link.querySelector('.brand-logo');
    if (!svg) return;

    if (prefersReducedMotion()) {
      svg.classList.add('brand-logo--instant');
      return;
    }

    var animated = link.getAttribute('data-logo-animated') !== 'false';
    if (!animated) {
      svg.classList.add('brand-logo--instant');
      return;
    }

    if (sessionStorage.getItem(STORAGE_KEY)) {
      setFinalState(svg);
    } else {
      svg.classList.add('brand-logo--animate');
      window.setTimeout(function () {
        setFinalState(svg);
        sessionStorage.setItem(STORAGE_KEY, '1');
      }, FULL_MS);
    }

    link.addEventListener('mouseenter', function () {
      if (prefersReducedMotion()) return;
      svg.classList.remove('brand-logo--done');
      svg.classList.add('brand-logo--hover-replay');
      window.setTimeout(function () {
        setFinalState(svg);
      }, HOVER_MS);
    });
  }

  window.brandLogoPlay = playFullAnimation;
  window.brandLogoReset = resetLogoState;
  window.brandLogoFinal = setFinalState;

  document.querySelectorAll('.brand-logo-link').forEach(initLogo);
})();
