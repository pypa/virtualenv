(function () {
  function dedent(text) {
    const lines = text.replace(/\s+$/u, "").split("\n");
    const indents = lines
      .filter((line) => line.trim())
      .map((line) => line.match(/^\s*/u)[0].length);

    if (!indents.length) {
      return text;
    }

    const indent = Math.min(...indents);
    return lines.map((line) => line.slice(indent)).join("\n");
  }

  function normalizeMermaidBlocks() {
    document.querySelectorAll("pre.mermaid").forEach((block) => {
      block.textContent = dedent(block.textContent);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", normalizeMermaidBlocks, {
      once: true,
    });
  } else {
    normalizeMermaidBlocks();
  }
})();
