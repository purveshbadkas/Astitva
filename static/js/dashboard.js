// ----------------------------
// Particles.js Initialization
// ----------------------------
particlesJS("particles-js", {
  particles: {
    number: { value: 100 },
    color: { value: "#FFF" },
    shape: { type: "circle" },
    opacity: { value: 0.3 },
    size: { value: 3 },
    line_linked: {
      enable: true,
      distance: 150,
      color: "#00ffff",
      opacity: 0.2,
      width: 1,
    },
    move: { enable: true, speed: 2 },
  },
  interactivity: {
    events: {
      onhover: { enable: true, mode: "repulse" },
      onclick: { enable: true, mode: "push" },
    },
    modes: {
      repulse: { distance: 100 },
      push: { particles_nb: 4 },
    },
  },
  retina_detect: true,
});

// ----------------------------
// GSAP Animations
// ----------------------------
gsap.from(".logo", { duration: 1, y: -50, opacity: 0, ease: "bounce" });
gsap.from(".header-center", { duration: 1, x: -50, opacity: 0, delay: 0.5 });
gsap.from(".nav-links a", {
  duration: 1,
  y: -30,
  opacity: 0,
  stagger: 0.2,
  delay: 0.5,
});
gsap.from(".circle-container", { duration: 1, scale: 0, opacity: 0, delay: 1 });
gsap.from(".card", {
  duration: 1,
  y: 50,
  opacity: 0,
  stagger: 0.3,
  delay: 1.5,
});
gsap.from(".about-us", { duration: 1, x: -100, opacity: 0, delay: 2 });
gsap.from(".team-section", { duration: 1, x: 100, opacity: 0, delay: 2.5 });
gsap.from("footer", { duration: 1, y: 50, opacity: 0, delay: 3 });

// ----------------------------
// Chatbot Integration
// ----------------------------
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    initializeChatbot();
  });

  function initializeChatbot() {
    const elements = {
      modal: document.getElementById("chatbot-modal"),
      overlay: document.getElementById("chatbot-overlay"),
      closeBtn: document.getElementById("chatbot-close"),
      searchBtn: document.getElementById("search-criminal-btn"),
      firBtn: document.getElementById("file-fir-btn"),
      criminalNameInput: document.getElementById("criminal-name"),
      firDetailsTextarea: document.getElementById("fir-details"),
      searchResult: document.getElementById("search-result"),
      firResult: document.getElementById("fir-result"),
      loadingIndicator: document.getElementById("loading-indicator"),
    };

    const missingElements = Object.entries(elements)
      .filter(([key, element]) => !element)
      .map(([key]) => key);

    if (missingElements.length > 0) {
      console.error("Chatbot: Missing DOM elements:", missingElements);
      return;
    }

    setupEventListeners(elements);
    setupCircleTrigger(elements);
    console.log("Chatbot initialized successfully");
  }

  function setupEventListeners(elements) {
    elements.closeBtn.addEventListener("click", () => closeModal(elements));
    elements.overlay.addEventListener("click", () => closeModal(elements));

    document.addEventListener("keydown", (event) => {
      if (
        event.key === "Escape" &&
        !elements.modal.classList.contains("hidden")
      ) {
        closeModal(elements);
      }
    });

    elements.searchBtn.addEventListener("click", () =>
      handleSearchCriminal(elements)
    );
    elements.criminalNameInput.addEventListener("keypress", (event) => {
      if (event.key === "Enter") handleSearchCriminal(elements);
    });

    elements.firBtn.addEventListener("click", () => handleFileFIR(elements));
    elements.firDetailsTextarea.addEventListener("keydown", (event) => {
      if (event.ctrlKey && event.key === "Enter") handleFileFIR(elements);
    });
  }

  function setupCircleTrigger(elements) {
    const circleContainer = document.querySelector(".circle-container");
    if (circleContainer) {
      circleContainer.addEventListener("click", () => openModal(elements));
    }
  }

  function openModal(elements) {
    elements.overlay.classList.remove("hidden");
    elements.modal.classList.remove("hidden");
    setTimeout(() => {
      elements.overlay.classList.add("show");
      elements.modal.classList.add("show");
    }, 10);
    document.body.style.overflow = "hidden";
    elements.modal.focus();
  }

  function closeModal(elements) {
    elements.overlay.classList.remove("show");
    elements.modal.classList.remove("show");
    setTimeout(() => {
      elements.overlay.classList.add("hidden");
      elements.modal.classList.add("hidden");
      document.body.style.overflow = "";
    }, 300);
    clearResults(elements);
  }

  function clearResults(elements) {
    elements.searchResult.className = "result-area hidden";
    elements.firResult.className = "result-area hidden";
  }

  function showLoading(elements, show = true) {
    if (show) elements.loadingIndicator.classList.remove("hidden");
    else elements.loadingIndicator.classList.add("hidden");
  }

  function handleSearchCriminal(elements) {
    const criminalName = elements.criminalNameInput.value.trim();
    if (!criminalName) {
      showResult(
        elements.searchResult,
        "Please enter a criminal name to search.",
        "error"
      );
      return;
    }

    elements.searchBtn.disabled = true;
    elements.searchBtn.textContent = "Searching...";
    showLoading(elements, true);

    fetch("/search_criminal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: criminalName }),
    })
      .then((res) => res.json())
      .then((data) => {
        showResult(
          elements.searchResult,
          data.reply || "No response received.",
          "success"
        );
      })
      .catch((err) =>
        showResult(elements.searchResult, `Error: ${err.message}`, "error")
      )
      .finally(() => {
        elements.searchBtn.disabled = false;
        elements.searchBtn.textContent = "Search";
        showLoading(elements, false);
      });
  }

  function handleFileFIR(elements) {
    const firDetails = elements.firDetailsTextarea.value.trim();
    if (!firDetails) {
      showResult(
        elements.firResult,
        "Please enter incident details to generate FIR.",
        "error"
      );
      return;
    }
    if (firDetails.length < 20) {
      showResult(
        elements.firResult,
        "Provide more detailed information (at least 20 characters).",
        "error"
      );
      return;
    }

    elements.firBtn.disabled = true;
    elements.firBtn.textContent = "Generating FIR...";
    showLoading(elements, true);

    fetch("/write_fir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ details: firDetails }),
    })
      .then((res) => res.json())
      .then((data) => {
        showResult(
          elements.firResult,
          data.reply || "No response received.",
          "success"
        );
      })
      .catch((err) =>
        showResult(elements.firResult, `Error: ${err.message}`, "error")
      )
      .finally(() => {
        elements.firBtn.disabled = false;
        elements.firBtn.textContent = "Generate FIR";
        showLoading(elements, false);
      });
  }

  function showResult(resultElement, message, type = "success") {
    resultElement.textContent = message;
    resultElement.className = `result-area ${type}`;
    resultElement.classList.remove("hidden");
    resultElement.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
})();

document.addEventListener("DOMContentLoaded", function () {
  const toggleBtn = document.getElementById("chatbot-toggle");
  const modal = document.getElementById("chatbot-modal");
  const overlay = document.getElementById("chatbot-overlay");
  const closeBtn = document.getElementById("chatbot-close");

  // Open modal
  toggleBtn.addEventListener("click", () => {
    modal.style.display = "flex";
    overlay.style.display = "block";
    document.body.style.overflow = "hidden";
  });

  // Close modal function
  function closeModal() {
    modal.style.display = "none";
    overlay.style.display = "none";
    document.body.style.overflow = "";
  }

  closeBtn.addEventListener("click", closeModal);
  overlay.addEventListener("click", closeModal);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  // Criminal search AJAX
const searchBtn = document.getElementById("search-criminal-btn");
searchBtn.addEventListener("click", async () => {
  const text = document.getElementById("criminal-name").value.trim();
  const resultDiv = document.getElementById("search-result");

  if (!text) {
    resultDiv.textContent = "Please enter something to search.";
    return;
  }

  resultDiv.classList.remove("hidden");
  resultDiv.textContent = "Searching...";

  try {
    const response = await fetch("/search_criminal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }), // <-- send full prompt
    });
    const data = await response.json();
    resultDiv.textContent = data.reply;
  } catch (err) {
    resultDiv.textContent = "Error fetching data.";
  }
});


  // FIR generation AJAX
  const firBtn = document.getElementById("file-fir-btn");
  firBtn.addEventListener("click", async () => {
    const details = document.getElementById("fir-details").value;
    const resultDiv = document.getElementById("fir-result");
    resultDiv.classList.remove("hidden");
    resultDiv.textContent = "Generating FIR...";
    try {
      const response = await fetch("/write_fir", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ details }),
      });
      const data = await response.json();
      resultDiv.innerHTML = `<pre>${data.reply}</pre><a href="${data.pdf_url}" target="_blank">Download PDF</a>`;
    } catch (err) {
      resultDiv.textContent = "Error generating FIR.";
    }
  });
});
