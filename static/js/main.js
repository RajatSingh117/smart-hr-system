/**
 * Smart HRMS - Global Enterprise Frontend Controller
 * Handles Theme Switching (Light/Dark mode), Password Visibility, and Responsive Sidebar Navigation.
 */

(function () {
  "use strict";

  const THEME_STORAGE_KEY = "smart_hr_theme";

  // 1. Theme Detection & Synchronization
  function getSystemPreference() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function getActiveTheme() {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === "dark" || saved === "light") {
      return saved;
    }
    return "light";
  }

  function setAppTheme(theme) {
    const safeTheme = theme === "dark" ? "dark" : "light";

    // Set attributes for both custom tokens and Bootstrap 5.3 native tokens
    document.documentElement.setAttribute("data-theme", safeTheme);
    document.documentElement.setAttribute("data-bs-theme", safeTheme);

    if (document.body) {
      document.body.setAttribute("data-theme", safeTheme);
      document.body.setAttribute("data-bs-theme", safeTheme);
    }

    try {
      localStorage.setItem(THEME_STORAGE_KEY, safeTheme);
    } catch (e) {
      // Handle private browsing or disabled storage gracefully
    }

    // Update toggle icons and accessibility labels
    const isDark = safeTheme === "dark";
    const sunIcons = document.querySelectorAll(".theme-icon-sun");
    const moonIcons = document.querySelectorAll(".theme-icon-moon");
    const toggleButtons = document.querySelectorAll("#theme-toggle, .btn-theme-toggle");

    sunIcons.forEach((el) => {
      if (isDark) el.classList.remove("d-none");
      else el.classList.add("d-none");
    });

    moonIcons.forEach((el) => {
      if (isDark) el.classList.add("d-none");
      else el.classList.remove("d-none");
    });

    toggleButtons.forEach((btn) => {
      btn.setAttribute(
        "aria-label",
        isDark ? "Switch to light mode" : "Switch to dark mode"
      );
      btn.setAttribute(
        "title",
        isDark ? "Switch to light mode" : "Switch to dark mode"
      );
    });

    // Notify external widgets (e.g., Chart.js)
    window.dispatchEvent(
      new CustomEvent("themeChanged", { detail: { theme: safeTheme } })
    );
  }

  function toggleTheme() {
    const currentTheme =
      document.documentElement.getAttribute("data-theme") || getActiveTheme();
    const nextTheme = currentTheme === "dark" ? "light" : "dark";
    setAppTheme(nextTheme);
  }

  // 2. Responsive Sidebar Controller
  function initSidebar() {
    const toggle = document.getElementById("sidebar-toggle");
    const sidebar = document.getElementById("hr-sidebar");
    const backdrop = document.getElementById("sidebar-backdrop");

    if (!sidebar) return;

    function openSidebar() {
      sidebar.classList.add("open");
      if (backdrop) backdrop.classList.add("active");
    }

    function closeSidebar() {
      sidebar.classList.remove("open");
      if (backdrop) backdrop.classList.remove("active");
    }

    if (toggle) {
      toggle.addEventListener("click", function (e) {
        e.stopPropagation();
        if (sidebar.classList.contains("open")) {
          closeSidebar();
        } else {
          openSidebar();
        }
      });
    }

    if (backdrop) {
      backdrop.addEventListener("click", closeSidebar);
    }

    // Auto-close on link navigation on mobile viewports
    sidebar.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        if (window.innerWidth < 992) {
          closeSidebar();
        }
      });
    });
  }

  // 3. Password Visibility Toggle
  function initPasswordToggles() {
    document.addEventListener("click", function (e) {
      const toggleBtn = e.target.closest(".btn-password-toggle");
      if (!toggleBtn) return;

      const targetId = toggleBtn.getAttribute("data-target");
      const input = targetId
        ? document.getElementById(targetId)
        : toggleBtn.closest(".input-group")?.querySelector("input");

      if (input) {
        const isPassword = input.getAttribute("type") === "password";
        input.setAttribute("type", isPassword ? "text" : "password");

        const eyeIcon = toggleBtn.querySelector("i");
        if (eyeIcon) {
          if (isPassword) {
            eyeIcon.classList.remove("bi-eye");
            eyeIcon.classList.add("bi-eye-slash");
            toggleBtn.setAttribute("title", "Hide password");
          } else {
            eyeIcon.classList.remove("bi-eye-slash");
            eyeIcon.classList.add("bi-eye");
            toggleBtn.setAttribute("title", "Show password");
          }
        }
      }
    });
  }

  // 4. Global Event Delegation for Theme Toggles (ensures zero dropped clicks)
  document.addEventListener("click", function (e) {
    const themeBtn = e.target.closest("#theme-toggle, .btn-theme-toggle");
    if (themeBtn) {
      e.preventDefault();
      toggleTheme();
    }
  });

  // 5. System Theme Listener (adapts when OS preference changes and user has no saved choice)
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
      try {
        if (!localStorage.getItem(THEME_STORAGE_KEY)) {
          setAppTheme(e.matches ? "dark" : "light");
        }
      } catch (err) {}
    });
  }

  // Initialization
  function initAll() {
    setAppTheme(getActiveTheme());
    initSidebar();
    initPasswordToggles();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }

  // Expose toggle on window for programmatic access or testing
  window.SmartHR = {
    setTheme: setAppTheme,
    toggleTheme: toggleTheme,
    getTheme: getActiveTheme,
  };
})();
