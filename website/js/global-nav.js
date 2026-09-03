/* ════════════════════════════════════════════════════════════════════
   VLSC Global Nav + UX Enhancements
   Shared across all project sites (portal, MRRC, SunMRRC, SunsdrMobile).
   Injects: global top nav, scroll-progress bar, back-to-top button,
   scroll-reveal (IntersectionObserver), active-link highlighting,
   navbar scrolled state, mobile-menu overlay.
   Self-contained — no dependencies. Site identified via <body data-site>
   or location.pathname. Language via <html lang> or /zh/ in path.
   ════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  // ── Site detection ──
  var SITE = document.body.getAttribute('data-site');
  if (!SITE) {
    var p = location.pathname.replace(/\/+$/, '');
    if (p === '' || p === '/index.html' || /(^|\/)portal\//.test(p)) SITE = 'portal';
    else if (/\/agentic\.html/.test(p)) SITE = 'agentic';
    else if (/\/mrrc\//.test(p)) SITE = 'mrrc';
    else if (/\/sunmrrc\//.test(p)) SITE = 'sunmrrc';
    else if (/\/sunsdrmobile\//.test(p)) SITE = 'sunsdrmobile';
    else if (/\/mrrc_ft710\//.test(p)) SITE = 'mrrc_ft710';
    else if (/\/sdd\//.test(p)) SITE = 'sunmrrc';
    else SITE = 'portal';
  }

  // ── Language detection ──
  var isCN = (document.documentElement.getAttribute('lang') || '').indexOf('zh') === 0
    || /\/zh\//.test(location.pathname);

  // Absolute paths (sites live under www.vlsc.net)
  var PATHS = {
    portal: '/',
    agentic: '/agentic.html',
    mrrc: '/mrrc/',
    mrrc_ft710: '/mrrc_ft710/',
    sunmrrc: '/sunmrrc/',
    sunsdrmobile: '/sunsdrmobile/'
  };

  var L = isCN ? {
    brand: 'VLSC 项目',
    projects: '项目',
    back: '返回顶部'
  } : {
    brand: 'VLSC Projects',
    projects: 'Projects',
    back: 'Back to top'
  };

  // ── 0. Fallback CSS (only when octen.css is not loaded) ──
  // Ensures the global nav + utilities render on pages that use a different
  // design system (e.g. MRRC docs pages with style.css, EFHW with Tailwind).
  var hasOcten = Array.prototype.some.call(
    document.querySelectorAll('link[rel="stylesheet"]'),
    function (l) { return /octen\.css(\?|$)/.test(l.getAttribute('href') || ''); }
  );
  if (!hasOcten) {
    var fb = document.createElement('style');
    // Self-contained: hardcoded colors so it never clashes with a page's own
    // design tokens. Only --gn-h/--nav-h are exposed as variables.
    fb.textContent =
      ':root{--gn-h:36px;--nav-h:64px;}' +
      '.vlsc-gn{position:fixed;top:0;left:0;right:0;z-index:120;height:var(--gn-h);' +
      'background:linear-gradient(180deg,rgba(0,0,0,0.96),rgba(10,10,10,0.92));' +
      'border-bottom:1px solid #262626;backdrop-filter:blur(16px);' +
      '-webkit-backdrop-filter:blur(16px);font-size:0.8125rem;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}' +
      '.vlsc-gn-inner{max-width:1200px;margin:0 auto;padding:0 2rem;height:var(--gn-h);' +
      'display:flex;align-items:center;justify-content:space-between;gap:1rem;}' +
      '.vlsc-gn-brand{display:inline-flex;align-items:center;gap:0.4rem;font-weight:700;color:#fff;text-decoration:none;white-space:nowrap;}' +
      '.vlsc-gn-brand i{color:#f39c12;font-size:0.85rem;}' +
      '.vlsc-gn-brand .dot{color:#f39c12;margin:0 0.35rem;opacity:0.5;}' +
      '.vlsc-gn-links{display:flex;align-items:center;gap:1.25rem;list-style:none;margin:0;padding:0;}' +
      '.vlsc-gn-links a{color:#a3a3a3;font-weight:500;text-decoration:none;position:relative;padding:0.25rem 0;transition:color 0.2s;white-space:nowrap;}' +
      '.vlsc-gn-links a::after{content:"";position:absolute;left:0;right:0;bottom:-3px;height:2px;background:#f39c12;transform:scaleX(0);transform-origin:center;transition:transform 0.25s;border-radius:2px;}' +
      '.vlsc-gn-links a:hover{color:#fff;}' +
      '.vlsc-gn-links a:hover::after,.vlsc-gn-links a.is-active::after{transform:scaleX(1);}' +
      '.vlsc-gn-links a.is-active{color:#f39c12;}' +
      '.vlsc-gn-gh{color:#a3a3a3;text-decoration:none;transition:color 0.2s;display:inline-flex;align-items:center;}' +
      '.vlsc-gn-gh:hover{color:#fff;}' +
      'body.vlsc-gn-on{padding-top:var(--gn-h)!important;}' +
      'body.vlsc-gn-on .navbar,body.vlsc-gn-on .header{top:var(--gn-h)!important;}' +
      '.vlsc-scroll-progress{position:fixed;top:0;left:0;z-index:200;height:2px;width:0%;' +
      'background:linear-gradient(90deg,#f39c12,#e67e22);pointer-events:none;}' +
      '.vlsc-to-top{position:fixed;right:1.5rem;bottom:1.5rem;z-index:110;width:44px;height:44px;' +
      'border-radius:50%;background:#1a1a1a;border:1px solid #262626;color:#f39c12;' +
      'display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:1rem;' +
      'opacity:0;visibility:hidden;transform:translateY(12px);transition:all 0.3s;' +
      'backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);}' +
      '.vlsc-to-top.show{opacity:1;visibility:visible;transform:translateY(0);}' +
      '.vlsc-to-top:hover{border-color:#f39c12;background:rgba(243,156,18,0.15);}' +
      '@media(max-width:768px){.vlsc-gn-links{gap:0.85rem;}.vlsc-gn-inner{padding:0 1.25rem;}.vlsc-to-top{right:1rem;bottom:1rem;}}';
    (document.head || document.documentElement).appendChild(fb);
  }

  // Shared styling for diagrams that are rendered as inline SVG instead of
  // browser text/pre blocks. Injected here so generated docs and EFHW pages
  // get the same treatment without editing every page template.
  var svgDiagramStyle = document.createElement('style');
  svgDiagramStyle.textContent =
    '.ascii-svg-diagram{display:block;width:100%;height:auto;max-width:100%;' +
    'background:linear-gradient(135deg,rgba(10,14,20,.96),rgba(13,20,30,.92));' +
    'border:1px solid rgba(34,211,238,.24);border-radius:14px;margin:1em 0;' +
    'box-shadow:0 18px 50px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.05);' +
    'overflow:visible;}' +
    '.ascii-svg-diagram text{font-family:"JetBrains Mono","SFMono-Regular",Consolas,monospace;' +
    'font-size:14px;fill:#dbeafe;}' +
    '.ascii-svg-diagram .diagram-title{font-weight:700;fill:#22d3ee;}' +
    '.ascii-svg-diagram .diagram-line{fill:#9ca3af;}' +
    '.ascii-svg-diagram-wrap{overflow-x:auto;margin:1em 0;}' +
    '.ascii-svg-source{display:none!important;}';
  (document.head || document.documentElement).appendChild(svgDiagramStyle);

  // ── 1. Global top nav ──
  var gn = document.createElement('div');
  gn.className = 'vlsc-gn';
  gn.innerHTML =
    '<div class="vlsc-gn-inner container">' +
      '<a class="vlsc-gn-brand" href="' + PATHS.portal + '" title="' + L.brand + '">' +
        '<i class="fas fa-satellite-dish"></i>' +
        '<span>VLSC<span class="dot">·</span>Projects</span>' +
      '</a>' +
      '<nav class="vlsc-gn-links">' +
        siteLink('agentic', 'Agentic') +
        siteLink('mrrc', 'MRRC') +
        siteLink('mrrc_ft710', 'FT-710') +
        siteLink('sunmrrc', 'SunMRRC') +
        siteLink('sunsdrmobile', 'SunsdrMobile') +
      '</nav>' +
      '<a class="vlsc-gn-gh" href="https://github.com/cheenle" target="_blank" rel="noopener" title="GitHub">' +
        '<i class="fab fa-github"></i>' +
      '</a>' +
    '</div>';

  function siteLink(key, label) {
    var active = (key === SITE) ? ' is-active' : '';
    return '<a href="' + PATHS[key] + '" data-site="' + key + '" class="' + active.trim() + '">' + label + '</a>';
  }

  // Insert as first child of body
  document.body.insertBefore(gn, document.body.firstChild);
  document.body.classList.add('vlsc-gn-on');

  // ── 2. Scroll progress bar ──
  var sp = document.createElement('div');
  sp.className = 'vlsc-scroll-progress';
  document.body.appendChild(sp);

  // ── 3. Back-to-top ──
  var bt = document.createElement('button');
  bt.type = 'button';
  bt.className = 'vlsc-to-top';
  bt.setAttribute('aria-label', L.back);
  bt.title = L.back;
  bt.innerHTML = '<i class="fas fa-arrow-up"></i>';
  bt.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
  document.body.appendChild(bt);

  // ── Scroll handler (throttled via rAF) ──
  var navbar = document.querySelector('.navbar, .header');
  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      var st = window.scrollY || document.documentElement.scrollTop;
      var h = document.documentElement.scrollHeight - window.innerHeight;
      sp.style.width = (h > 0 ? (st / h * 100) : 0) + '%';
      if (navbar) navbar.classList.toggle('scrolled', st > 40);
      bt.classList.toggle('show', st > 600);
      ticking = false;
    });
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // ── 4. Scroll reveal ──
  var revealSel = '.section .card, .section .demo-link, .section .feature-card, ' +
    '.section .eco-track, .section .arch-card, .section .step, ' +
    '.section .perf-card, .section .screen-card, .section .doc-card, ' +
    '.section .role-card, .section .card-lite, .section .tech-tag';
  var revealEls = document.querySelectorAll(revealSel);
  if ('IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    revealEls.forEach(function (el) { el.classList.add('vlsc-reveal'); });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    revealEls.forEach(function (el) { io.observe(el); });
  }

  // ── 5. Active section highlighting in site nav (anchor links) ──
  try {
    var anchorLinks = Array.prototype.slice.call(document.querySelectorAll('.nav-links a[href^="#"]'));
    if (anchorLinks.length) {
      var sections = anchorLinks.map(function (a) {
        return { link: a, el: document.querySelector(a.getAttribute('href')) };
      }).filter(function (o) { return o.el; });
      var navIO = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) {
            anchorLinks.forEach(function (a) { a.classList.remove('active'); });
            var match = sections.filter(function (o) { return o.el === e.target; })[0];
            if (match) match.link.classList.add('active');
          }
        });
      }, { threshold: 0.4 });
      sections.forEach(function (o) { navIO.observe(o.el); });
    }
  } catch (e) {}

  // ── 6. Mobile menu: toggle + close-on-link-click ──
  // Some pages define onclick="toggleMobileMenu()" inline; only attach our
  // own toggle when the button has no inline handler (avoids double-toggle).
  var toggle = document.querySelector('.mobile-menu-toggle');
  var navLinks = document.querySelector('.nav-links');
  if (toggle && navLinks) {
    if (!toggle.getAttribute('onclick')) {
      toggle.addEventListener('click', function () {
        navLinks.classList.toggle('active');
        toggle.classList.toggle('is-open');
      });
    }
    // Always close the menu after a link is clicked (enhancement)
    navLinks.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        navLinks.classList.remove('active');
        toggle.classList.remove('is-open');
      });
    });
  }

  // ── 7. Keep global-nav links in sync if injected on a /zh/ page ──
  // (links point to absolute site roots, which always show EN; that's fine
  //  — the per-site 中文 toggle lives in each site's own navbar.)

  // ── 8. Convert ASCII diagrams to inline SVG ──
  // Converts only diagram-like blocks; code examples such as JSON and shell
  // commands remain untouched.
  function isDiagramText(text) {
    if (!text) return false;
    return /[┌┐└┘├┤┬┴┼│─▶◀▼▲]|\[[^\]]+\]\s*[─-]{2,}/.test(text);
  }

  function trimDiagramLines(text) {
    var lines = text.replace(/\r\n/g, '\n').replace(/\u00a0/g, ' ').split('\n');
    while (lines.length && !lines[0].trim()) lines.shift();
    while (lines.length && !lines[lines.length - 1].trim()) lines.pop();
    var indents = lines.filter(function (l) { return l.trim(); }).map(function (l) {
      var m = l.match(/^\s*/);
      return m ? m[0].length : 0;
    });
    var minIndent = indents.length ? Math.min.apply(Math, indents) : 0;
    return lines.map(function (l) { return l.slice(minIndent); });
  }

  function svgEscape(text) {
    return text.replace(/[&<>]/g, function (ch) {
      return ch === '&' ? '&amp;' : ch === '<' ? '&lt;' : '&gt;';
    });
  }

  var asciiSvgId = 0;
  function makeDiagramSvg(lines, label) {
    asciiSvgId += 1;
    var bgId = 'asciiSvgBg' + asciiSvgId;
    var glowId = 'asciiSvgGlow' + asciiSvgId;
    var charW = 8.6;
    var lineH = 20;
    var padX = 22;
    var padY = 22;
    var maxLen = lines.reduce(function (n, line) { return Math.max(n, line.length); }, 0);
    var width = Math.max(560, Math.ceil(maxLen * charW + padX * 2));
    var height = Math.max(72, lines.length * lineH + padY * 2);
    var text = lines.map(function (line, i) {
      var cls = i === 0 && /MRRC|Architecture|架构|Connection|连接|Integration|集成|服务|组件|系统|拓扑/.test(line)
        ? 'diagram-title'
        : 'diagram-line';
      return '<text class="' + cls + '" x="' + padX + '" y="' + (padY + 14 + i * lineH) + '" xml:space="preserve">' + svgEscape(line) + '</text>';
    }).join('');
    return '<svg class="ascii-svg-diagram" role="img" aria-label="' + svgEscape(label || 'SVG diagram') + '" ' +
      'viewBox="0 0 ' + width + ' ' + height + '" width="' + width + '" height="' + height + '" ' +
      'xmlns="http://www.w3.org/2000/svg">' +
      '<defs><linearGradient id="' + bgId + '" x1="0" y1="0" x2="1" y2="1">' +
      '<stop offset="0" stop-color="#0a0e14"/><stop offset="1" stop-color="#102033"/></linearGradient>' +
      '<filter id="' + glowId + '" x="-20%" y="-20%" width="140%" height="140%">' +
      '<feGaussianBlur stdDeviation="18" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>' +
      '</defs>' +
      '<rect x="1" y="1" width="' + (width - 2) + '" height="' + (height - 2) + '" rx="14" fill="url(#' + bgId + ')"/>' +
      '<circle cx="' + (width - 70) + '" cy="54" r="80" fill="#22d3ee" opacity=".08" filter="url(#' + glowId + ')"/>' +
      '<g>' + text + '</g>' +
      '</svg>';
  }

  function convertAsciiDiagrams() {
    var candidates = Array.prototype.slice.call(document.querySelectorAll('pre, .code-block, .diagram, [style*="white-space:pre"]'));
    candidates.forEach(function (el) {
      if (el.classList.contains('ascii-svg-source') || el.closest('.ascii-svg-diagram-wrap')) return;
      var text = el.textContent || '';
      if (!isDiagramText(text)) return;
      var lines = trimDiagramLines(text);
      if (!lines.length) return;
      var wrap = document.createElement('div');
      wrap.className = 'ascii-svg-diagram-wrap';
      var heading = el.previousElementSibling && /^H[1-6]$/.test(el.previousElementSibling.tagName)
        ? el.previousElementSibling.textContent.trim()
        : 'SVG diagram';
      wrap.innerHTML = makeDiagramSvg(lines, heading);
      el.classList.add('ascii-svg-source');
      el.parentNode.insertBefore(wrap, el.nextSibling);
    });
  }

  convertAsciiDiagrams();

  // ── 9. Google AdSense ──
  if (location.hostname === 'www.vlsc.net' && !document.querySelector('script[src*="adsbygoogle"]')) {
    var adsenseScript = document.createElement('script');
    adsenseScript.async = true;
    adsenseScript.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-7442510147240155';
    adsenseScript.crossOrigin = 'anonymous';
    document.head.appendChild(adsenseScript);
  }

})();
