# CHERRY AI local Windows commands

These commands run locally in the Windows backend before the AI provider is called, so recognized commands do not require an API key.

## Supported

- Open allow-listed applications, folders, and websites (Chrome, Edge, VS Code, Notepad, Calculator, Explorer, Settings, Gmail, YouTube, Google, Flipkart, Amazon, etc.).
- Search Google, YouTube, Flipkart, and Amazon by opening the browser to a search page.
- Basic arithmetic and current local time.
- Lock the Windows workstation and save a screenshot.
- Set Windows master volume from 0–100%, mute to zero, unmute to the last non-zero level (or 50% if unknown), and volume up/down.
- Set a timer from 1 second to 24 hours, or schedule an alarm using a time such as `5 PM` or `17:00`. Windows Task Scheduler is used for timers/alarm notifications that are at least one minute away; shorter timers are in-memory and are lost if the backend stops.

## Not directly implemented

- Wi-Fi and Bluetooth commands open the relevant Windows Settings page; CHERRY AI does not switch the radio state itself.
- Shutdown and restart requests are confirmation-only messages. The current local router does not execute power actions.
- Windows scheduled alarms require the backend to run on Windows, the user to be logged in for the interactive notification, and the computer to be awake at the scheduled time. Power-management settings may delay them.
- The local-command router is not a replacement for permissioned browser interaction or the paired-device task executor. Task completion still requires a verified receipt from the registered executor.

## Example phrases

- `Open Chrome`
- `Search YouTube for workout music`
- `Open Flipkart and search for body spray under 1000 rupees`
- `Set volume to 70 percent`
- `Set timer for 20 minutes`
- `Set alarm for 5 PM`
- `Lock my PC`
- `Take screenshot`
