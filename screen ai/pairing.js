(() => {
    "use strict";
    const trigger = document.getElementById("phone-pair-generate");
    const panel = document.getElementById("phone-pair-code-wrap");
    const statusNode = document.getElementById("phone-pair-status");
    const panelStatus = document.getElementById("pair-panel-status");
    const expiryNode = document.getElementById("phone-pair-expiry");
    const qrNode = document.getElementById("phone-pair-qr");
    const authArea = document.getElementById("pair-auth-area");
    const accountArea = document.getElementById("pair-account-ready");
    const qrArea = document.getElementById("pair-qr-area");
    const modeNode = document.getElementById("pair-auth-mode");
    const emailNode = document.getElementById("pair-auth-email");
    const passwordNode = document.getElementById("pair-auth-password");
    const codeNode = document.getElementById("pair-auth-code");
    const authStatus = document.getElementById("pair-auth-status");
    const authButton = document.getElementById("pair-auth-submit");
    const qrButton = document.getElementById("pair-qr-create");
    const backendInput = document.getElementById("pair-backend-url");
    let currentRequestId = null;
    let countdownTimer = null;
    let pollingTimer = null;
    let expiresAt = 0;

    if (!trigger || !panel) return;
    if (backendInput) backendInput.value = API_BASE;

    function session() {
        return {
            token: sessionStorage.getItem("cherry_pairing_session") || "",
            email: sessionStorage.getItem("cherry_pairing_email") || ""
        };
    }

    function setStatus(message) {
        if (statusNode) statusNode.textContent = message;
        if (panelStatus) panelStatus.textContent = message;
    }

    function renderAccount() {
        const current = session();
        const signedIn = Boolean(current.token);
        if (authArea) authArea.classList.toggle("hidden", signedIn);
        if (accountArea) accountArea.classList.toggle("hidden", !signedIn);
        const label = document.getElementById("pair-account-email");
        if (label) label.textContent = current.email;
        if (signedIn) setStatus("Signed in. Generate a new QR code when your Android phone is ready.");
    }

    async function api(path, method, body, needsAuth) {
        const headers = { "Accept": "application/json", "Content-Type": "application/json" };
        if (needsAuth) {
            const token = session().token;
            if (!token) throw new Error("Sign in to your CHERRY AI account first.");
            headers.Authorization = "Bearer " + token;
        }
        const response = await fetch(API_BASE + path, {
            method: method,
            headers: headers,
            body: body ? JSON.stringify(body) : undefined,
            cache: "no-store"
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "CHERRY AI request failed (HTTP " + response.status + ").");
        return data;
    }

    document.getElementById("pair-backend-save")?.addEventListener("click", () => {
        const value = (backendInput?.value || "").trim().replace(/\/+$/, "");
        try {
            const parsed = new URL(value);
            if (parsed.protocol !== "https:" && parsed.protocol !== "http:") throw new Error();
            API_BASE = value;
            localStorage.setItem("cherry_api_base", value);
            setStatus("Backend URL saved for this browser.");
        } catch (_) {
            setStatus("Enter a valid backend URL beginning with http:// or https://.");
        }
    });

    modeNode?.addEventListener("change", () => {
        const mode = modeNode.value;
        if (passwordNode) passwordNode.classList.toggle("hidden", mode === "Verify email");
        if (codeNode) codeNode.classList.toggle("hidden", mode !== "Verify email");
        if (authButton) authButton.textContent = mode;
        if (passwordNode) passwordNode.autocomplete = mode === "Create account" ? "new-password" : "current-password";
    });

    authButton?.addEventListener("click", async () => {
        const mode = modeNode?.value || "Sign in";
        const email = (emailNode?.value || "").trim();
        const password = passwordNode?.value || "";
        const code = (codeNode?.value || "").trim();
        authButton.disabled = true;
        if (authStatus) authStatus.textContent = "Connecting securely…";
        try {
            let data;
            if (mode === "Create account") {
                data = await api("/identity/register", "POST", { email: email, password: password }, false);
                if (modeNode) modeNode.value = "Verify email";
                modeNode?.dispatchEvent(new Event("change"));
            } else if (mode === "Verify email") {
                data = await api("/identity/verify-email", "POST", { email: email, code: code }, false);
                if (modeNode) modeNode.value = "Sign in";
                modeNode?.dispatchEvent(new Event("change"));
            } else {
                data = await api("/identity/login", "POST", { email: email, password: password }, false);
                if (!data.access_token) throw new Error("The backend did not return an account session.");
                sessionStorage.setItem("cherry_pairing_session", data.access_token);
                sessionStorage.setItem("cherry_pairing_email", data.account?.email || email);
                renderAccount();
            }
            if (authStatus) authStatus.textContent = data.message || "Request completed.";
        } catch (error) {
            if (authStatus) authStatus.textContent = String(error.message || error);
        } finally {
            authButton.disabled = false;
        }
    });

    document.getElementById("pair-auth-logout")?.addEventListener("click", async () => {
        try {
            if (session().token) await api("/identity/logout", "POST", {}, true);
        } catch (_) {}
        sessionStorage.removeItem("cherry_pairing_session");
        sessionStorage.removeItem("cherry_pairing_email");
        stopTimers();
        if (qrArea) qrArea.classList.add("hidden");
        renderAccount();
    });

    function stopTimers() {
        if (countdownTimer) clearInterval(countdownTimer);
        if (pollingTimer) clearInterval(pollingTimer);
        countdownTimer = null;
        pollingTimer = null;
    }

    async function createQr() {
        if (!session().token) {
            renderAccount();
            return;
        }
        if (qrButton) {
            qrButton.disabled = true;
            qrButton.textContent = "Generating…";
        }
        stopTimers();
        currentRequestId = null;
        if (qrNode) qrNode.innerHTML = "";
        if (qrArea) qrArea.classList.add("hidden");
        try {
            const data = await api("/identity/pairing/requests", "POST", { label: "Android phone" }, true);
            if (!data.request_id || !data.qr_payload) throw new Error("The backend returned an incomplete QR pairing request.");
            if (typeof QRCode === "undefined") throw new Error("QR display library did not load. Refresh this page and try again.");
            new QRCode(qrNode, {
                text: JSON.stringify(data.qr_payload),
                width: 224,
                height: 224,
                colorDark: "#07111d",
                colorLight: "#ffffff",
                correctLevel: QRCode.CorrectLevel.M
            });
            currentRequestId = data.request_id;
            expiresAt = Date.now() + 120000;
            if (qrArea) qrArea.classList.remove("hidden");
            setStatus("Scan this QR code in CHERRY AI on Android. An approval email is sent after scanning.");
            const updateCountdown = () => {
                const remaining = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
                if (expiryNode) expiryNode.textContent = "QR expires in " + Math.floor(remaining / 60) + ":" + String(remaining % 60).padStart(2, "0");
                if (remaining === 0 && countdownTimer) {
                    clearInterval(countdownTimer);
                    countdownTimer = null;
                }
            };
            updateCountdown();
            countdownTimer = setInterval(updateCountdown, 500);
            pollingTimer = setInterval(async () => {
                if (!currentRequestId) return;
                try {
                    const result = await api("/identity/pairing/requests/" + encodeURIComponent(currentRequestId), "GET", null, true);
                    if (result.state === "exchanged") {
                        setStatus("Connected! Your Android phone is now linked to this account.");
                        stopTimers();
                        currentRequestId = null;
                    } else if (result.state === "pending_approval") {
                        setStatus("Phone scanned. Check your email and explicitly approve the connection.");
                    } else if (result.state === "denied" || result.state === "expired" || result.state === "email_failed") {
                        setStatus(result.state === "denied" ? "The connection was denied. No device was linked." : "This QR or approval request expired. Generate a new QR code.");
                        stopTimers();
                        currentRequestId = null;
                    }
                } catch (error) {
                    setStatus(String(error.message || error));
                    stopTimers();
                }
            }, 2000);
        } catch (error) {
            setStatus(String(error.message || error));
        } finally {
            if (qrButton) {
                qrButton.disabled = false;
                qrButton.textContent = "Generate new 2-minute QR";
            }
        }
    }

    qrButton?.addEventListener("click", createQr);
    trigger.addEventListener("click", () => {
        const opening = panel.classList.contains("hidden");
        panel.classList.toggle("hidden");
        if (opening) {
            renderAccount();
            if (session().token) void createQr();
        }
    });
    renderAccount();
})();