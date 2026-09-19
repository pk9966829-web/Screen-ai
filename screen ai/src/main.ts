import "./styles.css";

const app = document.querySelector<HTMLDivElement>("#app");

if (!app) {
  throw new Error("App container not found");
}

type AIState = "ready" | "watching" | "thinking";

let state: AIState = "ready";

app.innerHTML = `
  <div class="screen-ai">

    <div class="ambient ambient-one"></div>
    <div class="ambient ambient-two"></div>
    <div class="grid-overlay"></div>

    <header class="topbar">

      <div class="logo-area">
        <div class="logo-orbit">
          <div class="logo-core"></div>
        </div>

        <div>
          <div class="logo-name">SCREEN AI</div>
          <div class="logo-subtitle">INTELLIGENT SCREEN COMPANION</div>
        </div>
      </div>

      <div class="top-actions">

        <div class="connection">
          <span class="connection-dot"></span>
          SYSTEM READY
        </div>

        <button class="round-button" id="settingsButton">
          ⚙
        </button>

      </div>

    </header>


    <main class="main">

      <section class="companion-section">

        <div class="status-pill" id="statusPill">
          <span class="pulse-dot"></span>
          <span id="statusText">READY TO HELP</span>
        </div>


        <div class="companion">

          <div class="energy-ring ring-one"></div>
          <div class="energy-ring ring-two"></div>
          <div class="energy-ring ring-three"></div>

          <div class="companion-shadow"></div>

          <div class="character" id="character">

            <div class="head">

              <div class="forehead-glow"></div>

              <div class="eye eye-left">
                <div class="pupil"></div>
              </div>

              <div class="eye eye-right">
                <div class="pupil"></div>
              </div>

              <div class="smile"></div>

            </div>

            <div class="body">

              <div class="core-light"></div>

              <div class="body-highlight"></div>

            </div>

          </div>

        </div>


        <div class="welcome">

          <div class="tiny-label">YOUR DIGITAL COMPANION</div>

          <h1 id="headline">
            Hi, I'm <span>Screen AI.</span>
          </h1>

          <p id="subtitle">
            I'm here to understand your screen,
            follow what you're doing, and help when you need me.
          </p>

        </div>

      </section>


      <section class="interaction">

        <div class="command-box">

          <div class="command-icon">
            ✦
          </div>

          <input
            id="commandInput"
            type="text"
            placeholder="Ask Screen AI anything..."
            autocomplete="off"
          />

          <button class="mic-button" id="micButton">
            ◉
          </button>

          <button class="send-button" id="sendButton">
            →
          </button>

        </div>

        <div class="suggestions">

          <button data-command="What is happening on my screen?">
            <span>◉</span>
            What's on my screen?
          </button>

          <button data-command="Help me with what I'm doing">
            <span>✦</span>
            Help me with this
          </button>

          <button data-command="Start watching my screen">
            <span>◌</span>
            Start screen awareness
          </button>

        </div>

      </section>


      <section class="information">

        <div class="info-panel awareness-panel">

          <div class="panel-heading">

            <div class="panel-icon">
              ◉
            </div>

            <div>
              <div class="panel-label">SCREEN AWARENESS</div>
              <div class="panel-title" id="awarenessTitle">
                Ready to observe
              </div>
            </div>

            <div class="panel-state" id="awarenessState">
              OFF
            </div>

          </div>

          <p id="awarenessDescription">
            Screen AI can observe your screen when you ask it to.
          </p>

          <button class="panel-button" id="observeButton">
            Start observing
          </button>

        </div>


        <div class="info-panel task-panel">

          <div class="panel-heading">

            <div class="panel-icon">
              ✦
            </div>

            <div>
              <div class="panel-label">CURRENT TASK</div>
              <div class="panel-title" id="taskTitle">
                Nothing in progress
              </div>
            </div>

            <div class="panel-state">
              IDLE
            </div>

          </div>

          <p id="taskDescription">
            Give Screen AI a goal and it can follow your progress.
          </p>

          <button class="panel-button" id="taskButton">
            Start a task
          </button>

        </div>

      </section>


      <section class="activity" id="activityPanel">

        <div class="activity-header">
          <div>
            <div class="panel-label">ACTIVITY</div>
            <div class="activity-title">
              Screen AI is waiting for you
            </div>
          </div>

          <div class="activity-time">
            NOW
          </div>
        </div>

        <div class="activity-line">
          <div class="timeline-dot"></div>

          <div>
            <strong>Assistant ready</strong>
            <p>
              Ask a question or start screen awareness.
            </p>
          </div>
        </div>

      </section>

    </main>


    <footer class="footer">

      <div>
        <span class="footer-dot"></span>
        Screen AI Core
      </div>

      <div>
        LOCAL MODE
      </div>

      <div>
        v0.1.0
      </div>

    </footer>

  </div>
`;


/* -----------------------------------------
   Elements
----------------------------------------- */

const character =
  document.querySelector<HTMLDivElement>("#character");

const statusText =
  document.querySelector<HTMLSpanElement>("#statusText");

const statusPill =
  document.querySelector<HTMLDivElement>("#statusPill");

const headline =
  document.querySelector<HTMLHeadingElement>("#headline");

const subtitle =
  document.querySelector<HTMLParagraphElement>("#subtitle");

const commandInput =
  document.querySelector<HTMLInputElement>("#commandInput");

const sendButton =
  document.querySelector<HTMLButtonElement>("#sendButton");

const micButton =
  document.querySelector<HTMLButtonElement>("#micButton");

const observeButton =
  document.querySelector<HTMLButtonElement>("#observeButton");

const awarenessTitle =
  document.querySelector<HTMLDivElement>("#awarenessTitle");

const awarenessDescription =
  document.querySelector<HTMLParagraphElement>("#awarenessDescription");

const awarenessState =
  document.querySelector<HTMLDivElement>("#awarenessState");

const taskButton =
  document.querySelector<HTMLButtonElement>("#taskButton");

const taskTitle =
  document.querySelector<HTMLDivElement>("#taskTitle");

const taskDescription =
  document.querySelector<HTMLParagraphElement>("#taskDescription");


/* -----------------------------------------
   State
----------------------------------------- */

function setState(newState: AIState) {

  state = newState;

  character?.classList.remove(
    "state-ready",
    "state-watching",
    "state-thinking"
  );

  character?.classList.add(`state-${newState}`);

  statusPill?.classList.remove(
    "watching",
    "thinking"
  );

  if (newState === "ready") {

    statusText!.textContent = "READY TO HELP";

    headline!.innerHTML =
      `Hi, I'm <span>Screen AI.</span>`;

    subtitle!.textContent =
      "I'm here to understand your screen, follow what you're doing, and help when you need me.";

  }

  if (newState === "watching") {

    statusPill?.classList.add("watching");

    statusText!.textContent = "WATCHING YOUR SCREEN";

    headline!.innerHTML =
      `I'm <span>watching.</span>`;

    subtitle!.textContent =
      "I'll keep an eye on what's happening and let you know when I can help.";

  }

  if (newState === "thinking") {

    statusPill?.classList.add("thinking");

    statusText!.textContent = "THINKING";

    headline!.innerHTML =
      `Let me <span>think.</span>`;

    subtitle!.textContent =
      "I'm processing your request...";
  }
}


/* -----------------------------------------
   Send command
----------------------------------------- */

function sendCommand(command?: string) {

  const text =
    command ??
    commandInput?.value.trim();

  if (!text) {
    return;
  }

  setState("thinking");

  window.setTimeout(() => {

    if (
      text.toLowerCase().includes("watch") ||
      text.toLowerCase().includes("screen awareness")
    ) {

      startWatching();

      return;
    }

    setState("ready");

    headline!.innerHTML =
      `I'm ready for <span>your next move.</span>`;

    subtitle!.textContent =
      `I received: "${text}"`;

    commandInput!.value = "";

  }, 900);
}


sendButton?.addEventListener(
  "click",
  () => sendCommand()
);


commandInput?.addEventListener(
  "keydown",
  (event) => {

    if (event.key === "Enter") {
      sendCommand();
    }

  }
);


/* -----------------------------------------
   Suggestions
----------------------------------------- */

document
  .querySelectorAll<HTMLButtonElement>("[data-command]")
  .forEach((button) => {

    button.addEventListener(
      "click",
      () => {

        const command =
          button.dataset.command;

        if (command) {
          commandInput!.value = command;
          sendCommand(command);
        }

      }
    );

  });


/* -----------------------------------------
   Screen awareness
----------------------------------------- */

function startWatching() {

  setState("watching");

  awarenessTitle!.textContent =
    "Screen awareness active";

  awarenessDescription!.textContent =
    "Screen AI is ready to observe what you're doing.";

  awarenessState!.textContent =
    "ACTIVE";

  observeButton!.textContent =
    "Stop observing";

  observeButton!.classList.add("active");

  commandInput!.value = "";

}


observeButton?.addEventListener(
  "click",
  () => {

    if (
      awarenessState!.textContent === "ACTIVE"
    ) {

      setState("ready");

      awarenessTitle!.textContent =
        "Ready to observe";

      awarenessDescription!.textContent =
        "Screen AI can observe your screen when you ask it to.";

      awarenessState!.textContent =
        "OFF";

      observeButton!.textContent =
        "Start observing";

      observeButton!.classList.remove("active");

    } else {

      startWatching();

    }

  }
);


/* -----------------------------------------
   Task
----------------------------------------- */

taskButton?.addEventListener(
  "click",
  () => {

    const active =
      taskButton.textContent === "End task";

    if (active) {

      taskButton.textContent =
        "Start a task";

      taskTitle!.textContent =
        "Nothing in progress";

      taskDescription!.textContent =
        "Give Screen AI a goal and it can follow your progress.";

      return;
    }

    taskButton.textContent =
      "End task";

    taskTitle!.textContent =
      "Task is active";

    taskDescription!.textContent =
      "Screen AI is ready to follow your goal.";

    setState("watching");

  }
);


/* -----------------------------------------
   Microphone placeholder
----------------------------------------- */

micButton?.addEventListener(
  "click",
  () => {

    micButton.classList.toggle("active");

    if (micButton.classList.contains("active")) {

      micButton.textContent = "●";

      subtitle!.textContent =
        "Voice interaction will be connected here.";

    } else {

      micButton.textContent = "◉";

    }

  }
);


/* -----------------------------------------
   Settings
----------------------------------------- */

document
  .querySelector("#settingsButton")
  ?.addEventListener(
    "click",
    () => {

      subtitle!.textContent =
        "Settings will become available here as Screen AI grows.";

    }
  );