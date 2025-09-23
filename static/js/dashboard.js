document.addEventListener("DOMContentLoaded", function () {
  console.log("Dashboard.js loaded!");

  // ---------------- Particles & Animations ----------------
  window.onload = function () {
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
        modes: { repulse: { distance: 100 }, push: { particles_nb: 4 } },
      },
      retina_detect: true,
    });

    gsap.from(".logo", { duration: 1, y: -50, opacity: 0, ease: "power2.out" });
    gsap.from(".header-center", {
      duration: 1,
      x: -50,
      opacity: 0,
      ease: "back.out(1.2)",
      delay: 0.3,
    });
    gsap.from(".circle-container", {
      duration: 1,
      scale: 0,
      opacity: 0,
      ease: "back.out(1.2)",
      delay: 0.5,
    });
    gsap.from(".card", {
      duration: 1,
      y: 50,
      opacity: 0,
      stagger: 0.25,
      ease: "power2.out",
      delay: 1,
    });
  };

const toggleBtn = document.getElementById("chatbot-toggle");
const modalEl = document.getElementById("chatbot-modal");
const overlay = document.getElementById("chatbot-overlay");
const closeBtn = document.getElementById("chatbot-close");
const chatThread = document.getElementById("chatbot-thread");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
chatInput.addEventListener("input", () => {
chatInput.style.height = "auto";
chatInput.style.height = chatInput.scrollHeight + "px";
chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault(); // stop newline
    chatForm.dispatchEvent(new Event("submit")); // trigger form submit
    chatInput.value = ""; // clear after send
    chatInput.style.height = "auto"; // reset height
  }
});
});const loadingIndicator = document.getElementById("loading-indicator");

let chatMode = null;
let processStarted = false;

function addMessage(sender, text) {
  const msgEl = document.createElement("div");
  msgEl.className = `message ${sender}`;
  msgEl.innerHTML = text;
  chatThread.appendChild(msgEl);
  chatThread.scrollTop = chatThread.scrollHeight;
}

function showOptionPrompt() {
  addMessage(
    "assistant",
    `I can help you with the following. Pick an option <br>
      <button class="chat-option" data-mode="report">1️⃣ Generate a Crime Report</button><br>
      <button class="chat-option" data-mode="criminal">2️⃣ Get Criminal Info</button>`
  );

  // Apply style after buttons are added
  setTimeout(() => {
    document.querySelectorAll(".chat-option").forEach((btn) => {
      btn.style.backgroundColor = "#31dfefff"; // blue background
      btn.style.color = "black"; // white text
      btn.style.border = "none"; // no border
      btn.style.padding = "10px 15px";
      btn.style.margin = "5px 0";
      btn.style.borderRadius = "8px"; // rounded corners
      btn.style.cursor = "pointer";
    });
  }, 0);
}


function openChat() {
  modalEl.classList.add("active");
  overlay.classList.add("active");
  chatThread.innerHTML = `<div class="message assistant">Hello! I’m Astitva 👋. How can I help you today?</div>`;
  chatMode = null;
  processStarted = false;
  setTimeout(showOptionPrompt, 300);
}

function closeChat() {
  modalEl.classList.remove("active");
  overlay.classList.remove("active");
}

toggleBtn.addEventListener("click", openChat);
closeBtn.addEventListener("click", closeChat);
overlay.addEventListener("click", closeChat);

chatThread.addEventListener("click", function (e) {
  if (e.target.classList.contains("chat-option")) {
    chatMode = e.target.dataset.mode;
    addMessage("user", e.target.innerText);

    if (chatMode === "report") {
      processStarted = false;
      addMessage(
        "assistant",
        "Starting FIR process... Type 'start_fir_process' to begin."
      );
    } else {
      addMessage(
        "assistant",
        "Please type the name of the person you want info about."
      );
    }
  }
});

chatForm.addEventListener("submit", async function (e) {
  e.preventDefault();
  let message = chatInput.value.trim();
  if (!message) return;
  addMessage("user", message);
  chatInput.value = "";
  loadingIndicator.style.display = "inline";

  if (chatMode === "report" && !processStarted) {
    if (message.toLowerCase() !== "start_fir_process") {
      addMessage(
        "assistant",
        "Please start FIR process by typing 'start_fir_process'."
      );
      loadingIndicator.style.display = "none";
      return;
    } else {
      processStarted = true;
    }
  }

  try {
    const response = await fetch(
      chatMode === "report" ? "/chat_fir" : "/search_criminal",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          chatMode === "report" ? { message } : { text: message }
        ),
      }
    );
    const data = await response.json();
    loadingIndicator.style.display = "none";

    if (chatMode === "report" && data.download_link) {
      addMessage(
        "assistant",
        `${data.reply}<br><a href="${data.download_link}" target="_blank">Download FIR PDF</a>`
      );
    } else if (chatMode === "report" && data.next_question) {
      addMessage("assistant", data.next_question);
    } else {
      addMessage("assistant", data.reply);
    }
  } catch (err) {
    loadingIndicator.style.display = "none";
    addMessage("assistant", "⚠️ Server error. Try again.");
  }
});

});
