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
let screenStream: MediaStream | null = null;
let captureTimer: number | null = null;
let captureInProgress = false;

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

async function askScreenAI(message?: string) {
  const question = (message ?? askInput?.value ?? "").trim();
  if (!question) {
    askInput?.focus();
    return;
  }

  setStatus("THINKING...");
  mascot?.classList.add("thinking");
  addTimelineItem("You asked VOSI", question, "violet");
  if (askInput) askInput.value = "";

  try {
    const response = await fetch("http://127.0.0.1:8001/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: question, include_screen: true })
    });
    if (!response.ok) {
      throw new Error(`VOSI backend returned HTTP ${response.status}`);
    }

    const data: any = await response.json();
    const brain = data?.brain ?? {};
    const answer = brain.understanding || brain.suggestion || brain.error ||
      data?.error || "VOSI could not answer that question.";

    addTimelineItem(
      data.success && brain.success !== false ? "VOSI response" : "VOSI needs attention",
      answer,
      data.success && brain.success !== false ? "cyan" : "violet"
    );

    const guide = brain.guidance;
    const validGuidance = guide &&
      Number(guide.confidence) >= 0.60 &&
      Number.isFinite(Number(guide.target_x)) &&
      Number.isFinite(Number(guide.target_y)) &&
      Number(guide.target_x) >= 0 && Number(guide.target_x) <= 1000 &&
      Number(guide.target_y) >= 0 && Number(guide.target_y) <= 1000;

    if (validGuidance && window.__TAURI__) {
      try {
        await window.__TAURI__.core.invoke("show_guide");
        // Give the transparent guide webview time to appear before sending its target.
        await new Promise(resolve => window.setTimeout(resolve, 300));
        await window.__TAURI__.event.emit("vosi-guidance", {
          target_x: Number(guide.target_x),
          target_y: Number(guide.target_y),
          target_label: String(guide.target_label || "Next step"),
          instruction: String(guide.instruction || "Click the highlighted control"),
          confidence: Number(guide.confidence)
        });
        addTimelineItem(
          "Click target highlighted",
          String(guide.instruction || guide.target_label || "Follow the glowing highlight."),
          "green"
        );
      } catch (guideError) {
        console.error("VOSI could not show the click guide:", guideError);
        addTimelineItem(
          "Click guide unavailable",
          "VOSI found a target, but the overlay could not be opened. Check the guide window permissions and restart VOSI.",
          "violet"
        );
      }
    } else if (window.__TAURI__) {
      try {
        await window.__TAURI__.event.emit("vosi-guidance-clear");
        await window.__TAURI__.core.invoke("hide_guide");
      } catch (guideError) {
        console.warn("Could not clear the VOSI click guide:", guideError);
      }
    }

    if (!data.success || brain.success === false) {
      setStatus("AI REQUEST FAILED");
    } else {
      setStatus(awarenessEnabled ? "SCREEN AWARENESS ACTIVE" : "READY TO HELP");
    }
  } catch (error) {
    console.error("VOSI question failed:", error);
    addTimelineItem(
      "Could not reach VOSI",
      "Make sure the backend is running at http://127.0.0.1:8001 and try again. " + String(error),
      "violet"
    );
    setStatus("BACKEND CONNECTION ERROR");
  } finally {
    mascot?.classList.remove("thinking");
    if (statusText?.textContent === "BACKEND CONNECTION ERROR" ||
        statusText?.textContent === "AI REQUEST FAILED") {
      // Keep the error visible so it is easier to diagnose.
    } else {
      setStatus(awarenessEnabled ? "SCREEN AWARENESS ACTIVE" : "READY TO HELP");
    }
  }
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

async function startScreenCapture() {
  if (screenStream) return;
  if (!navigator.mediaDevices?.getDisplayMedia) {
    throw new Error("Screen sharing is not available in this environment.");
  }

  const stream = await navigator.mediaDevices.getDisplayMedia({
    video: { frameRate: { ideal: 2, max: 5 } },
    audio: false
  });
  screenStream = stream;

  const video = document.createElement("video");
  video.srcObject = stream;
  video.muted = true;
  await video.play();

  const canvas = document.createElement("canvas");
  const sendFrame = async () => {
    if (!screenStream || captureInProgress || !video.videoWidth || !video.videoHeight) return;
    captureInProgress = true;
    try {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const context = canvas.getContext("2d");
      if (!context) return;
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.78));
      if (!blob || !screenStream) return;
      const form = new FormData();
      form.append("file", blob, "screen.jpg");
      const response = await fetch("http://127.0.0.1:8001/screen", { method: "POST", body: form });
      if (!response.ok) throw new Error(`Screen upload failed (${response.status})`);
    } catch (error) {
      console.warn("VOSI screen frame upload failed:", error);
    } finally {
      captureInProgress = false;
    }
  };

  void sendFrame();
  captureTimer = window.setInterval(() => { void sendFrame(); }, 2000);
  stream.getVideoTracks()[0]?.addEventListener("ended", () => {
    void setAwareness(false, true);
  });
}

function stopScreenCapture() {
  if (captureTimer !== null) {
    window.clearInterval(captureTimer);
    captureTimer = null;
  }
  const oldStream = screenStream;
  screenStream = null;
  oldStream?.getTracks().forEach((track) => track.stop());
}

async function setAwareness(enabled: boolean, fromEndedTrack = false) {
  if (enabled === awarenessEnabled && (enabled ? !!screenStream : !screenStream)) return;

  if (enabled) {
    try {
      await startScreenCapture();
      awarenessEnabled = true;
      try {
        await fetch("http://127.0.0.1:8001/awareness", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: true })
        });
      } catch (error) {
        console.warn("Could not update VOSI backend awareness state:", error);
      }
      updateAwarenessUI();
      void notifyCompanion(true);
      if (window.__TAURI__) void window.__TAURI__.event.emit("observation-status", { active: true });
      addTimelineItem("Screen awareness started", "VOSI is capturing the screen you selected.", "green");
    } catch (error) {      awarenessEnabled = false;
      stopScreenCapture();
      updateAwarenessUI();
      setStatus("SCREEN SHARING NOT STARTED");
      addTimelineItem("Screen awareness not started", "Choose a screen in the sharing dialog and allow access. " + String(error), "violet");
      console.warn("VOSI could not start screen capture:", error);
      if (window.__TAURI__) void window.__TAURI__.event.emit("observation-status", { active: false });
    }
  } else {
    awarenessEnabled = false;
    stopScreenCapture();
    try {
      await fetch("http://127.0.0.1:8001/awareness", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: false })
      });
    } catch (error) {
      console.warn("Could not update VOSI backend awareness state:", error);
    }
    updateAwarenessUI();
    void notifyCompanion(false);
    if (window.__TAURI__) void window.__TAURI__.event.emit("observation-status", { active: false });
    if (!fromEndedTrack) addTimelineItem("Screen awareness stopped", "VOSI is no longer observing your screen.", "violet");
  }
}

function toggleAwareness() {
  void setAwareness(!awarenessEnabled);
}

awarenessToggle?.addEventListener("click", toggleAwareness);
observeBtn?.addEventListener("click", toggleAwareness);

if (window.__TAURI__) {
  window.__TAURI__.event.listen("companion-toggle-observe", (event: any) => {
    const requested = event?.payload?.observing;
    if (typeof requested === "boolean" && requested !== awarenessEnabled) {
      void setAwareness(requested);
    }
  });
}


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

async function notifyCompanion(show: boolean) {
  try {
    if (!window.__TAURI__) return;
    await window.__TAURI__.event.emit("show-companion", { show });
  } catch (error) {
    console.warn("Companion visibility update failed:", error);
  }
}

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