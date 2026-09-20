import "./styles.css";

declare global {
  interface Window {
    __TAURI__?: any;
  }
}


// =========================================================
// SCREEN AI — FRONTEND CONTROLLER
// =========================================================


// =========================================================
// DOM ELEMENTS
// =========================================================

const app = document.getElementById("app");

if (!app) {
  throw new Error("Screen AI app container was not found.");
}


const statusText =
  document.getElementById("statusText");


const mascot =
  document.getElementById("mascot");


const mascotInner =
  document.getElementById("mascotInner");


const askInput =
  document.getElementById(
    "askInput"
  ) as HTMLInputElement | null;


const sendBtn =
  document.getElementById(
    "sendBtn"
  ) as HTMLButtonElement | null;


const micBtn =
  document.getElementById(
    "micBtn"
  ) as HTMLButtonElement | null;


const awarenessToggle =
  document.getElementById(
    "awarenessToggle"
  ) as HTMLButtonElement | null;


const observeBtn =
  document.getElementById(
    "observeBtn"
  ) as HTMLButtonElement | null;


const taskBtn =
  document.getElementById(
    "taskBtn"
  ) as HTMLButtonElement | null;


const taskBadge =
  document.getElementById("taskBadge");


const taskHeading =
  document.getElementById("taskHeading");


const timeline =
  document.getElementById("timeline");


const bellBtn =
  document.getElementById(
    "bellBtn"
  ) as HTMLButtonElement | null;


const winMin =
  document.getElementById(
    "winMin"
  ) as HTMLButtonElement | null;


const winMax =
  document.getElementById(
    "winMax"
  ) as HTMLButtonElement | null;


const winClose =
  document.getElementById(
    "winClose"
  ) as HTMLButtonElement | null;


const restoreChip =
  document.getElementById(
    "restoreChip"
  ) as HTMLButtonElement | null;


// =========================================================
// STATE
// =========================================================

let awarenessEnabled = false;

let taskRunning = false;

let recording = false;


// =========================================================
// STATUS
// =========================================================

function setStatus(text: string) {
  if (statusText) {
    statusText.textContent = text;
  }
}


// =========================================================
// BACKGROUND STARS
// =========================================================

function createStars() {

  const stars =
    document.getElementById("stars");

  if (!stars) return;

  stars.innerHTML = "";


  for (let i = 0; i < 90; i++) {

    const star =
      document.createElement("span");

    star.className = "star";


    const size =
      Math.random() * 2.5 + 1;


    star.style.width =
      `${size}px`;

    star.style.height =
      `${size}px`;


    star.style.left =
      `${Math.random() * 100}%`;

    star.style.top =
      `${Math.random() * 100}%`;


    star.style.animationDelay =
      `${Math.random() * 4}s`;


    star.style.animationDuration =
      `${2 + Math.random() * 4}s`;


    if (Math.random() > 0.82) {

      star.classList.add(
        "bright"
      );

    }


    stars.appendChild(star);
  }
}


// =========================================================
// MASCOT STARS
// =========================================================

function createMascotStars() {

  const container =
    document.getElementById(
      "mStars"
    );

  if (!container) return;

  container.innerHTML = "";


  for (let i = 0; i < 28; i++) {

    const star =
      document.createElement("span");

    star.className = "star";


    const size =
      Math.random() * 2 + 1;


    star.style.width =
      `${size}px`;

    star.style.height =
      `${size}px`;


    star.style.left =
      `${20 + Math.random() * 60}%`;

    star.style.top =
      `${10 + Math.random() * 75}%`;


    star.style.animationDelay =
      `${Math.random() * 3}s`;


    container.appendChild(star);
  }
}


// =========================================================
// HTML ESCAPING
// =========================================================

function escapeHtml(value: string) {

  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll(
      "'",
      "&#039;"
    );
}


// =========================================================
// ACTIVITY TIMELINE
// =========================================================

function addTimelineItem(
  title: string,
  description: string,
  type:
    | "violet"
    | "cyan"
    | "green" = "violet"
) {

  if (!timeline) return;


  const item =
    document.createElement("li");


  item.className =
    `timeline-item ${type}`;


  item.innerHTML = `
    <span class="t-dot"></span>

    <div class="t-content">

      <strong>
        ${escapeHtml(title)}
      </strong>

      <p>
        ${escapeHtml(description)}
      </p>

    </div>
  `;


  timeline.prepend(item);
}


// =========================================================
// ASK SCREEN AI
// =========================================================

function askScreenAI(
  message?: string
) {

  const text =
    (
      message ??
      askInput?.value ??
      ""
    ).trim();


  if (!text) {

    askInput?.focus();

    return;
  }


  setStatus(
    "THINKING..."
  );


  mascot?.classList.add(
    "thinking"
  );


  addTimelineItem(
    "You asked Screen AI",
    text,
    "violet"
  );


  if (askInput) {

    askInput.value = "";
  }


  setTimeout(() => {

    setStatus(
      awarenessEnabled
        ? "SCREEN AWARENESS ACTIVE"
        : "READY TO HELP"
    );


    mascot?.classList.remove(
      "thinking"
    );


    addTimelineItem(
      "Screen AI is ready",
      "Your request has been received. The real AI brain will be connected here next.",
      "cyan"
    );

  }, 900);
}


// =========================================================
// SEND BUTTON
// =========================================================

sendBtn?.addEventListener(
  "click",
  () => {
    askScreenAI();
  }
);


// =========================================================
// ENTER TO SEND
// =========================================================

askInput?.addEventListener(
  "keydown",
  (event) => {

    if (event.key === "Enter") {

      event.preventDefault();

      askScreenAI();
    }

  }
);


// =========================================================
// QUICK ACTION CHIPS
// =========================================================

document
  .querySelectorAll<HTMLButtonElement>(
    ".chip"
  )
  .forEach((chip) => {

    chip.addEventListener(
      "click",
      () => {

        const question =
          chip.dataset.ask;


        if (!question) return;


        if (askInput) {

          askInput.value =
            question;
        }


        askScreenAI(
          question
        );
      }
    );

  });


// =========================================================
// SCREEN AWARENESS UI
// =========================================================

function updateAwarenessUI() {

  if (
    !awarenessToggle ||
    !observeBtn
  ) {
    return;
  }


  awarenessToggle.classList.toggle(
    "on",
    awarenessEnabled
  );


  awarenessToggle.setAttribute(
    "aria-checked",
    awarenessEnabled
      ? "true"
      : "false"
  );


  const label =
    awarenessToggle.querySelector(
      ".t-label"
    );


  if (label) {

    label.textContent =
      awarenessEnabled
        ? "ON"
        : "OFF";
  }


  observeBtn.textContent =
    awarenessEnabled
      ? "Stop observing"
      : "Start observing";


  observeBtn.classList.toggle(
    "danger",
    awarenessEnabled
  );


  setStatus(
    awarenessEnabled
      ? "SCREEN AWARENESS ACTIVE"
      : "READY TO HELP"
  );
}


// =========================================================
// TOGGLE SCREEN AWARENESS
// =========================================================

function toggleAwareness() {

  awarenessEnabled =
    !awarenessEnabled;


  updateAwarenessUI();


  if (awarenessEnabled) {

    addTimelineItem(
      "Screen awareness started",
      "Screen AI can now observe your screen.",
      "green"
    );

  } else {

    addTimelineItem(
      "Screen awareness stopped",
      "Screen AI is no longer observing your screen.",
      "violet"
    );

  }
}


awarenessToggle?.addEventListener(
  "click",
  toggleAwareness
);


observeBtn?.addEventListener(
  "click",
  toggleAwareness
);


// =========================================================
// TASK SYSTEM
// =========================================================

function toggleTask() {

  taskRunning =
    !taskRunning;


  if (
    !taskBadge ||
    !taskHeading ||
    !taskBtn
  ) {
    return;
  }


  if (taskRunning) {

    taskBadge.textContent =
      "ACTIVE";


    taskBadge.classList.add(
      "active"
    );


    taskHeading.textContent =
      "Understanding your goal";


    taskBtn.textContent =
      "Stop task";


    addTimelineItem(
      "Task started",
      "Screen AI is ready to follow your progress.",
      "cyan"
    );

  } else {

    taskBadge.textContent =
      "IDLE";


    taskBadge.classList.remove(
      "active"
    );


    taskHeading.textContent =
      "Nothing in progress";


    taskBtn.textContent =
      "Start a task";


    addTimelineItem(
      "Task stopped",
      "The current task has been stopped.",
      "violet"
    );

  }
}


taskBtn?.addEventListener(
  "click",
  toggleTask
);


// =========================================================
// MICROPHONE BUTTON
// =========================================================

micBtn?.addEventListener(
  "click",
  () => {

    recording =
      !recording;


    micBtn.classList.toggle(
      "recording",
      recording
    );


    if (recording) {

      setStatus(
        "LISTENING..."
      );


      addTimelineItem(
        "Voice input",
        "Screen AI is listening.",
        "cyan"
      );

    } else {

      setStatus(
        awarenessEnabled
          ? "SCREEN AWARENESS ACTIVE"
          : "READY TO HELP"
      );

    }

  }
);


// =========================================================
// NOTIFICATION BUTTON
// =========================================================

bellBtn?.addEventListener(
  "click",
  () => {

    bellBtn.classList.remove(
      "ring"
    );


    void bellBtn.offsetWidth;


    bellBtn.classList.add(
      "ring"
    );


    addTimelineItem(
      "Notifications checked",
      "There are no new Screen AI notifications.",
      "violet"
    );

  }
);


// =========================================================
// WINDOW CONTROLS
// =========================================================

function minimizeApp() {

  app.classList.add(
    "minimized"
  );


  restoreChip?.classList.add(
    "visible"
  );
}


function restoreApp() {

  app.classList.remove(
    "minimized"
  );


  app.classList.remove(
    "closed"
  );


  restoreChip?.classList.remove(
    "visible"
  );
}


function maximizeApp() {

  app.classList.toggle(
    "maximized"
  );
}


function closeApp() {

  app.classList.add(
    "closed"
  );


  restoreChip?.classList.add(
    "visible"
  );
}


winMin?.addEventListener(
  "click",
  minimizeApp
);


winMax?.addEventListener(
  "click",
  maximizeApp
);


winClose?.addEventListener(
  "click",
  closeApp
);


restoreChip?.addEventListener(
  "click",
  restoreApp
);


// =========================================================
// ROBOT HEAD MOUSE TRACKING
// =========================================================
//
// The robot's HEAD follows the user's mouse.
// The body stays mostly still.
// The eyes follow slightly more than the head.
// Everything is smoothly interpolated.
//

const robotHead =
  document.querySelector(
    ".head"
  ) as HTMLElement | null;


const robotEyes =
  document.querySelectorAll<HTMLElement>(
    ".eye"
  );


let targetHeadX = 0;
let targetHeadY = 0;

let currentHeadX = 0;
let currentHeadY = 0;


let targetEyeX = 0;
let targetEyeY = 0;

let currentEyeX = 0;
let currentEyeY = 0;


// =========================================================
// MOUSE MOVEMENT
// =========================================================

window.addEventListener(
  "mousemove",
  (event) => {

    const centerX =
      window.innerWidth / 2;


    const centerY =
      window.innerHeight / 2;


    const normalizedX =
      (
        event.clientX -
        centerX
      ) / centerX;


    const normalizedY =
      (
        event.clientY -
        centerY
      ) / centerY;


    // HEAD

    targetHeadX =
      Math.max(
        -18,
        Math.min(
          18,
          normalizedX * 18
        )
      );


    targetHeadY =
      Math.max(
        -12,
        Math.min(
          12,
          normalizedY * 12
        )
      );


    // EYES

    targetEyeX =
      Math.max(
        -7,
        Math.min(
          7,
          normalizedX * 7
        )
      );


    targetEyeY =
      Math.max(
        -5,
        Math.min(
          5,
          normalizedY * 5
        )
      );

  }
);


// =========================================================
// SMOOTH HEAD ANIMATION
// =========================================================

function animateRobotHead() {

  currentHeadX +=
    (
      targetHeadX -
      currentHeadX
    ) * 0.08;


  currentHeadY +=
    (
      targetHeadY -
      currentHeadY
    ) * 0.08;


  currentEyeX +=
    (
      targetEyeX -
      currentEyeX
    ) * 0.12;


  currentEyeY +=
    (
      targetEyeY -
      currentEyeY
    ) * 0.12;


  if (robotHead) {

    const headRotation =
      currentHeadX * 0.18;


    robotHead.style.transform = `
      translate(
        ${currentHeadX}px,
        ${currentHeadY}px
      )
      rotate(
        ${headRotation}deg
      )
    `;

  }


  robotEyes.forEach(
    (eye) => {

      eye.style.transform = `
        translate(
          ${currentEyeX}px,
          ${currentEyeY}px
        )
      `;

    }
  );


  requestAnimationFrame(
    animateRobotHead
  );
}


animateRobotHead();


// =========================================================
// NAVIGATION
// =========================================================

document
  .querySelectorAll<HTMLButtonElement>(
    ".nav-item"
  )
  .forEach((item) => {

    item.addEventListener(
      "click",
      () => {

        document
          .querySelectorAll(
            ".nav-item"
          )
          .forEach((nav) => {

            nav.classList.remove(
              "active"
            );

          });


        item.classList.add(
          "active"
        );


        const label =
          item.querySelector(
            "span"
          )?.textContent;


        if (label) {

          addTimelineItem(
            `${label} opened`,
            `Screen AI switched to ${label}.`,
            "violet"
          );

        }

      }
    );

  });


// =========================================================
// TAURI
// =========================================================

async function setupTauriControls() {

  if (!window.__TAURI__) {

    return;
  }


  try {

    console.log(
      "Screen AI running inside Tauri."
    );

  } catch {

    console.log(
      "Tauri controls unavailable."
    );

  }
}


// =========================================================
// INITIALIZATION
// =========================================================

createStars();

createMascotStars();

updateAwarenessUI();

setStatus(
  "READY TO HELP"
);


setupTauriControls();


addTimelineItem(
  "Assistant ready",
  "Ask a question or start screen awareness.",
  "violet"
);


console.log(
  "Screen AI frontend initialized."
);