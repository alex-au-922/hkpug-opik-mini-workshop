async function writeToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch (error) {
      // Browser permissions can reject the modern API on embedded pages.
    }
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.append(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) {
    throw new Error("Clipboard copy was rejected.");
  }
}

async function copyCaseTemplate(caseId) {
  const source = document.querySelector(`#template-${caseId}`);
  const button = document.querySelector(`[data-copy-case="${caseId}"]`);

  try {
    await writeToClipboard(source.textContent.trim());
    button.textContent = "Copied";
  } catch (error) {
    button.textContent = "Copy failed";
  }

  window.setTimeout(() => {
    button.textContent = "Copy template";
  }, 1600);
}

document.querySelectorAll("[data-copy-case]").forEach((button) => {
  button.addEventListener("click", () => copyCaseTemplate(button.dataset.copyCase));
});

document.querySelectorAll("[data-case-link]").forEach((link) => {
  link.addEventListener("click", () => {
    document.querySelector(`#case-${link.dataset.caseLink}`).open = true;
  });
});
