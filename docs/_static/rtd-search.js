document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.querySelector(
    ".sidebar-search input[type='search']",
  );
  if (searchInput) {
    searchInput.addEventListener("focus", () => {
      document.dispatchEvent(new CustomEvent("readthedocs-search-show"));
      searchInput.blur();
    });
  }
});
