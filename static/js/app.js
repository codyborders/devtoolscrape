(function () {
  console.debug("DevTools Scraper frontend bootstrap");

  function simulateLongTask(durationMs) {
    const end = performance.now() + durationMs;
    while (performance.now() < end) {
      // Busy loop to generate a long animation frame for browser profiling.
    }
  }

  function seedProfiles() {
    setTimeout(() => simulateLongTask(650), 1000);
    setTimeout(() => simulateLongTask(650), 4000);
    setTimeout(() => simulateLongTask(650), 8000);
  }

  if (document.readyState === "complete") {
    seedProfiles();
  } else {
    window.addEventListener("load", seedProfiles, { once: true });
  }
})();

//# sourceMappingURL=app.js.map
