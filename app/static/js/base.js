window.APP_ROOT = document.documentElement.dataset.appRoot || "";

// Navbar dropdowns (same behaviour as the main Data Explorer)
document.querySelectorAll(".nav-dropdown").forEach((dropdown) => {
  const button = dropdown.querySelector(".nav-dropdown-button");
  if (!button) {
    return;
  }
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    dropdown.classList.remove("is-dismissed");
    const isOpen = dropdown.classList.toggle("is-open");
    button.setAttribute("aria-expanded", String(isOpen));
  });
  // Escape hides the menu even while hover/focus would keep it open, until the pointer or focus leaves
  dropdown.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") {
      return;
    }
    dropdown.classList.remove("is-open");
    dropdown.classList.add("is-dismissed");
    button.setAttribute("aria-expanded", "false");
    button.focus();
  });
  dropdown.addEventListener("mouseleave", () => {
    dropdown.classList.remove("is-dismissed");
  });
  dropdown.addEventListener("focusout", (event) => {
    if (!dropdown.contains(event.relatedTarget)) {
      dropdown.classList.remove("is-dismissed");
    }
  });
});

document.addEventListener("click", () => {
  document.querySelectorAll(".nav-dropdown.is-open").forEach((dropdown) => {
    dropdown.classList.remove("is-open");
    const button = dropdown.querySelector(".nav-dropdown-button");
    if (button) {
      button.setAttribute("aria-expanded", "false");
    }
  });
});

// Menu button that shows the nav links on narrow screens
document.querySelectorAll(".nav-toggle").forEach((toggle) => {
    const nav = toggle.closest(".top-nav");
    toggle.addEventListener("click", () => {
        const isOpen = nav.classList.toggle("is-nav-open");
        toggle.setAttribute("aria-expanded", String(isOpen));
    });
});
