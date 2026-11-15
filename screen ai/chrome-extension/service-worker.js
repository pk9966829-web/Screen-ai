const API = "http://127.0.0.1:8001";
let checking = false;

async function checkForVosiCommand() {
  if (checking) return;
  checking = true;
  try {
    const response = await fetch(API + "/browser/command", { cache: "no-store" });
    if (!response.ok) return;
    const data = await response.json();
    const command = data.command;
    if (!command?.request_id || !command.query) return;
    const url = "https://www.flipkart.com/search?q=" + encodeURIComponent(command.query) +
      "&vosi_request=" + encodeURIComponent(command.request_id);
    // Open a new Chrome tab so the user's current page is left untouched.
    await chrome.tabs.create({ url, active: true });
    await fetch(API + "/browser/ack/" + encodeURIComponent(command.request_id), { method: "POST" });
  } catch (error) {
    console.warn("VOSI bridge could not reach the local backend:", error);
  } finally {
    checking = false;
  }
}
chrome.alarms.create("vosi-poll", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === "vosi-poll") void checkForVosiCommand();
});
chrome.runtime.onInstalled.addListener(() => void checkForVosiCommand());
void checkForVosiCommand();