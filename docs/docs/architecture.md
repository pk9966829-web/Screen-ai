SCREEN AI — SYSTEM ARCHITECTURE

Overall System:

User
  ↓
Screen AI Client
  ↓
Observation Engine
  ↓
Context Engine
  ↓
AI Reasoning Engine
  ↓
Assistance Layer
  ↓
User

1. SCREEN AI CLIENT

The client runs on the user's device.

Initial platforms:
- Desktop
- Android

The client is responsible for:
- Screen observation
- User interaction
- Voice input
- Text input
- Showing the AI overlay
- Showing visual guidance

2. OBSERVATION ENGINE

The Observation Engine understands what is happening on the screen.

It should detect:
- Screen changes
- Active application
- Visible text
- Important UI elements
- Relevant user actions

It should not continuously upload full-resolution video unnecessarily.

Instead, observations should be triggered by meaningful changes or events.

3. CONTEXT ENGINE

The Context Engine maintains the user's ongoing task.

It should remember:
- Current application
- User's goal
- Previous actions
- Completed steps
- Current step
- Problems encountered
- Important information from earlier in the workflow

Example:

If a user is filling out a college application:

Step 1: Personal information — completed
Step 2: Education information — completed
Step 3: Document upload — current
Step 4: Payment — not started

The AI should understand this context.

4. AI REASONING ENGINE

The AI combines:

Current screen observation
+
Task context
+
User request
+
Previous observations

It then determines:
- What is happening?
- What is the user trying to do?
- Is there a problem?
- What should happen next?
- Should the AI proactively help?

5. ASSISTANCE LAYER

The AI can communicate through:

- Text
- Voice
- Visual indicators
- On-screen guidance

6. FUTURE ACTION ENGINE

Later, with explicit user permission, Screen AI can perform actions such as:

- Click
- Type
- Scroll
- Open applications
- Navigate websites
- Edit files

Every action should be followed by verification.

Agent Loop:

Observe
↓
Reason
↓
Act
↓
Verify
↓
Observe Again

7. BACKEND

The backend will eventually handle:

- AI requests
- User sessions
- Context management
- Authentication
- Database
- API communication

Initial backend technology:

Python + FastAPI

8. DATABASE

Initial development:

SQLite

Later:

PostgreSQL

9. CLIENT TECHNOLOGY

Desktop:

Tauri + TypeScript

Android:

Kotlin

10. DEVELOPMENT PRINCIPLE

Build the system gradually.

Version 0.1:
Observe screen → understand screen → answer user

Version 0.2:
Observe → maintain context → answer

Version 0.3:
Understand workflow → proactively guide

Version 0.4:
Text + voice + visual guidance

Version 0.5:
Controlled computer actions

Version 1.0:
AI coworker
