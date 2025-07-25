particlesJS("particles-js", {
    "particles": {
      "number": {
        "value": 150,  // Increased for high density
        "density": {
          "enable": true,
          "value_area": 800
        }
      },
      "color": {
        "value": "#00f0ff"
      },
      "shape": {
        "type": "circle"
      },
      "opacity": {
        "value": 0.5,
        "random": false
      },
      "size": {
        "value": 3,
        "random": true
      },
      "line_linked": {
        "enable": true,
        "distance": 100,  // Lower distance = more connections
        "color": "#00f0ff",
        "opacity": 0.4,
        "width": 1
      },
      "move": {
        "enable": true,
        "speed": 1.2,
        "direction": "none",
        "out_mode": "out"
      }
    },
    "interactivity": {
      "events": {
        "onhover": {
          "enable": true,
          "mode": "repulse"
        },
        "onclick": {
          "enable": true,
          "mode": "push"
        }
      },
      "modes": {
        "repulse": {
          "distance": 80
        },
        "push": {
          "particles_nb": 4
        }
      }
    },
    "retina_detect": true
    
  });
  