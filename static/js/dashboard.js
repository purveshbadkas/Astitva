// Initialize Particles Only for Dashboard
particlesJS("particles-js", {
  particles: {
    number: { value: 100 },
    color: { value: "#FFF" }, // Cyan-like color for dashboard
    shape: { type: "circle" },
    opacity: { value: 0.3 }, // Lower opacity only for dashboard
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

// GSAP Animations
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
