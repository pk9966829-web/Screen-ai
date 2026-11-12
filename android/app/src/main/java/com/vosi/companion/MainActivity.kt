package com.vosi.companion

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.Build
import android.media.AudioManager
import android.provider.ContactsContract
import android.provider.Settings
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import android.text.InputType
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import java.util.Calendar
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import kotlin.concurrent.thread

class MainActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var contactName: EditText
    private lateinit var phoneNumber: EditText
    private lateinit var whatsappMessage: EditText
    private lateinit var companionToken: EditText
    private lateinit var syncButton: Button
    private lateinit var messagesContainer: LinearLayout
    private lateinit var deviceBackendUrl: EditText
    private lateinit var devicePairingCode: EditText
    private lateinit var deviceStatus: TextView
    private lateinit var pairDeviceButton: Button
    private lateinit var heartbeatDeviceButton: Button
    private lateinit var disconnectDeviceButton: Button
    private lateinit var deviceCommandInput: EditText
    private lateinit var sendDeviceCommandButton: Button
    private lateinit var voiceConversationButton: Button
    @Volatile private var activityResumed = false
    @Volatile private var textToSpeechReady = false
    private var textToSpeech: TextToSpeech? = null
    private val contactsPermission = 100
    private val callPermission = 101
    private val voicePermission = 103
    private val voiceRequest = 104

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(28, 28, 28, 28)
            gravity = Gravity.TOP
        }
        val heading = TextView(this).apply {
            text = "VOSI Companion"
            textSize = 26f
        }
        val subtitle = TextView(this).apply {
            text = "Phone tools and your personal WhatsApp, with permissions you control."
            textSize = 15f
            setPadding(0, 10, 0, 18)
        }
        contactName = EditText(this).apply {
            hint = "Contact name (for example, Dad)"
            isSingleLine = true
        }
        phoneNumber = EditText(this).apply {
            hint = "Phone number with country code (e.g. 919876543210)"
            isSingleLine = true
            inputType = 3
        }
        status = TextView(this).apply {
            text = "Contacts are only read after you grant permission."
            textSize = 14f
            setPadding(0, 14, 0, 14)
        }

        val findButton = Button(this).apply {
            text = "Find contact"
            setOnClickListener { findContact() }
        }
        val callButton = Button(this).apply {
            text = "Call this number"
            setOnClickListener { confirmAndCall() }
        }

        root.addView(heading)
        root.addView(subtitle)

        root.addView(TextView(this).apply {
            text = "CONNECT THIS PHONE TO VOSI"
            textSize = 13f
            setPadding(0, 8, 0, 4)
        })
        deviceBackendUrl = EditText(this).apply {
            hint = "VOSI backend URL (USB ADB reverse: http://127.0.0.1:8001)"
            isSingleLine = true
            setText(
                getSharedPreferences("vosi_companion_settings", MODE_PRIVATE)
                    .getString("device_backend_url", "http://127.0.0.1:8001")
            )
        }
        devicePairingCode = EditText(this).apply {
            hint = "One-time VOSI phone pairing code"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            isSingleLine = true
        }
        pairDeviceButton = Button(this).apply {
            text = "Pair this phone with VOSI"
            setOnClickListener { pairPhoneDevice() }
        }
        deviceStatus = TextView(this).apply {
            textSize = 13f
            setPadding(0, 8, 0, 8)
        }
        deviceCommandInput = EditText(this).apply {
            hint = "Tell VOSI: set an alarm for 5 PM on my PC, or search body spray on Flipkart"
            minLines = 2
        }
        sendDeviceCommandButton = Button(this).apply {
            text = "Send command to my VOSI devices"
            setOnClickListener { sendDeviceTaskRequest() }
        }
        voiceConversationButton = Button(this).apply {
            text = "Talk to VOSI"
            setOnClickListener { startVoiceConversation() }
        }
        heartbeatDeviceButton = Button(this).apply {
            text = "Check VOSI connection"
            setOnClickListener { heartbeatPhoneDevice() }
        }
        disconnectDeviceButton = Button(this).apply {
            text = "Disconnect this phone"
            setOnClickListener { disconnectPhoneDevice() }
        }
        root.addView(deviceBackendUrl, matchWidth())
        root.addView(devicePairingCode, matchWidth())
        root.addView(pairDeviceButton, matchWidth())
        root.addView(heartbeatDeviceButton, matchWidth())
        root.addView(disconnectDeviceButton, matchWidth())
        root.addView(deviceStatus)
        root.addView(deviceCommandInput, matchWidth())
        root.addView(sendDeviceCommandButton, matchWidth())
        root.addView(voiceConversationButton, matchWidth())
        root.addView(Switch(this).apply {
            text = "Speak browser recommendations"
            isChecked = getSharedPreferences("vosi_companion_settings", MODE_PRIVATE)
                .getBoolean("spoken_browser_results", false)
            setOnCheckedChangeListener { _, enabled ->
                getSharedPreferences("vosi_companion_settings", MODE_PRIVATE)
                    .edit().putBoolean("spoken_browser_results", enabled).apply()
                deviceStatus.text = if (enabled) {
                    "Spoken browser recommendations enabled. VOSI speaks only while this app is open."
                } else {
                    "Spoken browser recommendations disabled."
                }
            }
        }, matchWidth())

        root.addView(TextView(this).apply {
            text = "PHONE"
            textSize = 13f
            setPadding(0, 12, 0, 4)
        })
        root.addView(contactName, matchWidth())
        root.addView(findButton, matchWidth())
        root.addView(phoneNumber, matchWidth())
        root.addView(callButton, matchWidth())

        root.addView(TextView(this).apply {
            text = "WHATSAPP"
            textSize = 13f
            setPadding(0, 24, 0, 4)
        })
        root.addView(TextView(this).apply {
            text = "VOSI reads WhatsApp notification previews. They stay on this phone unless you tap Sync with Desktop VOSI. It does not access WhatsApp's private chat database."
            textSize = 13f
            setPadding(0, 4, 0, 8)
        })
        root.addView(Button(this).apply {
            text = "Enable WhatsApp notification access"
            setOnClickListener { openNotificationAccessSettings() }
        }, matchWidth())
        root.addView(Button(this).apply {
            text = "Refresh recent WhatsApp messages"
            setOnClickListener { refreshWhatsAppMessages() }
        }, matchWidth())

        companionToken = EditText(this).apply {
            hint = "Paste your private desktop pairing token"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            isSingleLine = true
            setText(
                getSharedPreferences("vosi_companion_settings", MODE_PRIVATE)
                    .getString("pairing_token", "")
            )
        }
        root.addView(companionToken, matchWidth())

        syncButton = Button(this).apply {
            text = "Sync WhatsApp with Desktop VOSI"
            setOnClickListener { syncWhatsAppWithDesktop() }
        }
        root.addView(syncButton, matchWidth())
        root.addView(TextView(this).apply {
            text = "Send a new WhatsApp message"
            textSize = 14f
            setPadding(0, 12, 0, 2)
        })
        whatsappMessage = EditText(this).apply {
            hint = "Type the message to compose"
            minLines = 2
            gravity = Gravity.TOP
        }
        root.addView(whatsappMessage, matchWidth())
        root.addView(Button(this).apply {
            text = "Open WhatsApp chat"
            setOnClickListener { openWhatsAppChat() }
        }, matchWidth())
        root.addView(Button(this).apply {
            text = "Clear locally saved notification previews"
            setOnClickListener {
                WhatsAppNotificationListener.clearMessages(this@MainActivity)
                refreshWhatsAppMessages()
                status.text = "Saved WhatsApp notification previews cleared from this phone."
            }
        }, matchWidth())

        messagesContainer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, 8, 0, 8)
        }
        root.addView(messagesContainer, matchWidth())
        root.addView(status)

        val scroll = ScrollView(this).apply {
            isFillViewport = true
            addView(root)
        }
        setContentView(scroll)
        textToSpeech = TextToSpeech(this) { result ->
            if (result == TextToSpeech.SUCCESS) {
                val languageResult = textToSpeech?.setLanguage(Locale.getDefault())
                textToSpeechReady = languageResult != TextToSpeech.LANG_MISSING_DATA &&
                    languageResult != TextToSpeech.LANG_NOT_SUPPORTED
            }
        }
        refreshPairedDeviceStatus()
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 102)
        }
    }

    private val devicePollHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private val devicePollRunnable = object : Runnable {
        override fun run() {
            if (::deviceStatus.isInitialized && DeviceCredentialStore.load(this@MainActivity) != null) {
                heartbeatPhoneDevice()
                devicePollHandler.postDelayed(this, 20000L)
            }
        }
    }

    override fun onResume() {
        super.onResume()
        activityResumed = true
        refreshWhatsAppMessages()
        if (::deviceStatus.isInitialized) {
            refreshPairedDeviceStatus()
            devicePollHandler.removeCallbacks(devicePollRunnable)
            devicePollHandler.post(devicePollRunnable)
        }
    }

    override fun onPause() {
        activityResumed = false
        textToSpeech?.stop()
        devicePollHandler.removeCallbacks(devicePollRunnable)
        super.onPause()
    }

    private fun refreshPairedDeviceStatus() {
        val credential = DeviceCredentialStore.load(this)
        deviceStatus.text = if (credential == null) {
            "Phone is not paired with VOSI yet."
        } else {
            "Paired: ${credential.optString("label", "Android phone")}  •  Device ID: ${credential.optString("device_id")}"
        }
    }

    private fun backendBaseUrl(): String {
        val value = deviceBackendUrl.text.toString().trim().trimEnd('/')
        if (!(value.startsWith("http://") || value.startsWith("https://")) || value.length > 300) {
            throw IllegalArgumentException("Enter a valid backend URL beginning with http:// or https://.")
        }
        return value
    }

    private fun requestDeviceApi(
        baseUrl: String,
        path: String,
        method: String,
        token: String? = null,
        body: JSONObject? = null,
        readTimeoutMs: Int = 15000
    ): Pair<Int, String> {
        val connection = (URL(baseUrl + path).openConnection() as HttpURLConnection)
        try {
            connection.requestMethod = method
            connection.connectTimeout = 10000
            connection.readTimeout = readTimeoutMs
            if (token != null) connection.setRequestProperty("Authorization", "Bearer $token")
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() } ?: "HTTP $code"
            return Pair(code, text)
        } finally {
            connection.disconnect()
        }
    }

    private fun pairPhoneDevice() {
        val code = devicePairingCode.text.toString().trim()
        if (code.length < 20) {
            deviceStatus.text = "Paste the one-time pairing code generated by VOSI."
            return
        }
        val baseUrl = try {
            backendBaseUrl()
        } catch (error: Exception) {
            deviceStatus.text = error.message ?: "Invalid backend URL."
            return
        }
        pairDeviceButton.isEnabled = false
        deviceStatus.text = "Pairing this phone securely…"
        thread {
            try {
                val capabilities = JSONArray()
                    .put("phone.contacts.read")
                    .put("phone.call")
                    .put("phone.whatsapp.quick_reply")
                    .put("agent.task.request")
                    .put("device.alarm.create")
                    .put("device.volume.set")
                val payload = JSONObject()
                    .put("pairing_code", code)
                    .put("capabilities", capabilities)
                val (responseCode, responseText) = requestDeviceApi(
                    baseUrl, "/agent/devices/pair", "POST", body = payload
                )
                val response = JSONObject(responseText)
                if (responseCode !in 200..299 || !response.optBoolean("success")) {
                    throw IllegalStateException(response.optString("detail", "Pairing failed. Generate a new code in VOSI."))
                }
                val device = response.getJSONObject("device")
                val credential = JSONObject()
                    .put("backend_url", baseUrl)
                    .put("device_id", device.getString("device_id"))
                    .put("device_token", device.getString("device_token"))
                    .put("platform", device.getString("platform"))
                    .put("label", device.optString("label", "Android phone"))
                    .put("capabilities", device.optJSONArray("capabilities") ?: JSONArray())
                    .put("paired_at", device.optString("paired_at"))
                DeviceCredentialStore.save(this, credential.toString())
                getSharedPreferences("vosi_companion_settings", MODE_PRIVATE)
                    .edit().putString("device_backend_url", baseUrl).apply()
                runOnUiThread {
                    devicePairingCode.text.clear()
                    deviceStatus.text = "Phone paired successfully. Its credential is protected by Android Keystore."
                    refreshPairedDeviceStatus()
                    pairDeviceButton.isEnabled = true
                    heartbeatPhoneDevice()
                    devicePollHandler.removeCallbacks(devicePollRunnable)
                    devicePollHandler.postDelayed(devicePollRunnable, 20000L)
                }
            } catch (error: Exception) {
                runOnUiThread {
                    deviceStatus.text = "Could not pair phone: ${error.message ?: "backend unavailable"}"
                    pairDeviceButton.isEnabled = true
                }
            }
        }
    }

    private fun startVoiceConversation() {
        if (DeviceCredentialStore.load(this) == null) {
            deviceStatus.text = "Pair this phone with VOSI before starting a voice conversation."
            return
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), voicePermission)
            return
        }
        try {
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak to VOSI")
                putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            }
            startActivityForResult(intent, voiceRequest)
        } catch (error: Exception) {
            deviceStatus.text = "No Android speech recognition service is available: ${error.message ?: "unknown error"}"
        }
    }

    @Deprecated("Uses Android's system speech-recognition activity for broad device compatibility")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != voiceRequest) return
        if (resultCode != RESULT_OK) {
            deviceStatus.text = "Voice input was cancelled. Tap Talk to VOSI when you're ready."
            return
        }
        val transcript = data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            ?.firstOrNull()?.trim().orEmpty()
        if (transcript.isBlank()) {
            deviceStatus.text = "I didn't catch that. Please try speaking again."
            return
        }
        deviceCommandInput.setText(transcript)
        sendVoiceTurn(transcript)
    }

    private fun sendVoiceTurn(transcript: String) {
        val credential = DeviceCredentialStore.load(this)
        if (credential == null) {
            deviceStatus.text = "Your phone is no longer paired with VOSI."
            return
        }
        voiceConversationButton.isEnabled = false
        deviceStatus.text = "VOSI is thinking…"
        thread {
            try {
                val payload = JSONObject().put("transcript", transcript)
                val (code, body) = requestDeviceApi(
                    credential.getString("backend_url"),
                    "/companion/voice",
                    "POST",
                    token = credential.getString("device_token"),
                    body = payload,
                    readTimeoutMs = 45000
                )
                val response = JSONObject(body)
                if (code !in 200..299 || !response.optBoolean("success")) {
                    throw IllegalStateException(response.optString("detail",
                        response.optString("response", "VOSI could not answer this voice turn.")))
                }
                val answer = response.optString("response", "I'm here.")
                runOnUiThread {
                    deviceStatus.text = "You: $transcript\nVOSI: $answer"
                    voiceConversationButton.isEnabled = true
                    if (activityResumed && textToSpeechReady) {
                        textToSpeech?.speak(answer, TextToSpeech.QUEUE_FLUSH, null,
                            "vosi-voice-${System.currentTimeMillis()}")
                    }
                }
            } catch (error: Exception) {
                runOnUiThread {
                    deviceStatus.text = "Voice conversation failed: ${error.message ?: "backend unavailable"}"
                    voiceConversationButton.isEnabled = true
                }
            }
        }
    }

    private fun sendDeviceTaskRequest() {
        val query = deviceCommandInput.text.toString().trim()
        if (query.isBlank()) {
            deviceStatus.text = "Type a command for your paired VOSI devices first."
            return
        }
        val credential = DeviceCredentialStore.load(this)
        if (credential == null) {
            deviceStatus.text = "Pair this phone with VOSI first."
            return
        }

        val steps = JSONArray()
        val normalized = query.lowercase()
        val goal: String
        val alarmMatch = Regex(
            """(?:set|create)\s+(?:an?\s+)?alarm\s+(?:for\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?""",
            RegexOption.IGNORE_CASE
        ).find(query)

        if (alarmMatch != null) {
            var hour = alarmMatch.groupValues[1].toIntOrNull() ?: -1
            val minute = alarmMatch.groupValues[2].ifBlank { "0" }.toIntOrNull() ?: -1
            val meridiem = alarmMatch.groupValues[3].lowercase()
            if (meridiem == "pm" && hour in 1..11) hour += 12
            if (meridiem == "am" && hour == 12) hour = 0
            if (hour !in 0..23 || minute !in 0..59) {
                deviceStatus.text = "Use a valid alarm time, for example 5 PM."
                return
            }
            val target = if (normalized.contains("phone") || normalized.contains("mobile")) "android" else "desktop"
            goal = "Set a VOSI alarm for $query"
            steps.put(
                JSONObject()
                    .put("step_id", "set-device-alarm")
                    .put("capability", "device.alarm.create")
                    .put("target_platform", target)
                    .put("title", "Set an alarm on the paired $target device")
                    .put("arguments", JSONObject().put("hour", hour).put("minute", minute))
            )
        } else {
            val volumePercent = Regex(
                """(?:set|change)\s+(?:my\s+)?(?:phone|mobile)\s+volume\s+(?:to\s+)?(\d{1,3})\s*%?""",
                RegexOption.IGNORE_CASE
            ).find(query)
            val desktopVolume = Regex(
                """(?:set\s+(?:my\s+)?pc\s+volume\s+to\s+)?(?:volume\s+)?(up|down|mute|unmute)(?:\s+on\s+(?:my\s+)?pc)?""",
                RegexOption.IGNORE_CASE
            ).find(query)
            val timerMatch = Regex(
                """(?:set|start)\s+(?:a\s+)?timer\s+(?:for\s+)?(\d{1,5})\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)(?:\s+on\s+(?:my\s+)?pc)?""",
                RegexOption.IGNORE_CASE
            ).find(query)
            val searchMatch = Regex(
                """^(?:search|find)\s+(.+?)\s+on\s+flipkart\s*$""",
                RegexOption.IGNORE_CASE
            ).find(query)
            val openPageMatch = Regex(
                """^(?:open|go to|navigate to)\s+(https://\S+|[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?:\s+(?:in|on)\s+chrome)?\s*$""",
                RegexOption.IGNORE_CASE
            ).find(query)
            val readPageMatch = Regex(
                """^read\s+(?:this|the current|current)\s+page(?:\s+in\s+chrome)?\s*$""",
                RegexOption.IGNORE_CASE
            ).find(query)
            val powerAction = Regex("""\b(shut\s*down|shutdown|restart|reboot)\b.*\b(?:pc|computer|windows|desktop)\b|\b(?:pc|computer|windows|desktop)\b.*\b(shut\s*down|shutdown|restart|reboot)\b""", RegexOption.IGNORE_CASE).find(query)
            val settingsAction = when {
                Regex("""\bbluetooth\b.*\b(?:settings|on|off|enable|disable|open)\b""", RegexOption.IGNORE_CASE).containsMatchIn(query) -> "device.bluetooth.settings.open"
                Regex("""\bwi[ -]?fi\b.*\b(?:settings|on|off|enable|disable|open)\b""", RegexOption.IGNORE_CASE).containsMatchIn(query) -> "device.wifi.settings.open"
                else -> null
            }

            when {
                powerAction != null -> {
                    val requested = powerAction.groupValues[1].ifBlank { powerAction.groupValues[2] }.lowercase().replace(" ", "")
                    val capability = if (requested in setOf("shutdown", "shut down")) "device.pc.shutdown" else "device.pc.restart"
                    goal = if (capability == "device.pc.shutdown") "Request Windows PC shutdown" else "Request Windows PC restart"
                    steps.put(JSONObject().put("step_id", "windows-power-action").put("capability", capability)
                        .put("target_platform", "desktop")
                        .put("title", if (capability == "device.pc.shutdown") "Shut down Windows after PC confirmation" else "Restart Windows after PC confirmation")
                        .put("arguments", JSONObject()))
                }
                settingsAction != null -> {
                    goal = if (settingsAction.contains("bluetooth")) "Open Windows Bluetooth settings" else "Open Windows Wi-Fi settings"
                    steps.put(JSONObject().put("step_id", "open-windows-radio-settings").put("capability", settingsAction)
                        .put("target_platform", "desktop").put("title", goal).put("arguments", JSONObject()))
                }
                volumePercent != null -> {
                    val percent = volumePercent.groupValues[1].toIntOrNull() ?: -1
                    if (percent !in 0..100) {
                        deviceStatus.text = "Phone volume must be between 0% and 100%."
                        return
                    }
                    goal = "Set phone volume to $percent percent"
                    steps.put(
                        JSONObject()
                            .put("step_id", "set-phone-volume")
                            .put("capability", "device.volume.set")
                            .put("target_platform", "android")
                            .put("title", "Set this phone's media volume")
                            .put("arguments", JSONObject().put("volume", percent))
                    )
                }
                desktopVolume != null -> {
                    val action = desktopVolume.groupValues[1].lowercase()
                    goal = "Adjust Windows PC volume: $action"
                    steps.put(
                        JSONObject()
                            .put("step_id", "adjust-pc-volume")
                            .put("capability", "device.volume.action")
                            .put("target_platform", "desktop")
                            .put("title", "Adjust Windows PC volume")
                            .put("arguments", JSONObject().put("action", action))
                    )
                }
                timerMatch != null -> {
                    val amount = timerMatch.groupValues[1].toLongOrNull() ?: -1L
                    val unit = timerMatch.groupValues[2].lowercase()
                    val multiplier = when {
                        unit.startsWith("hour") || unit.startsWith("hr") -> 3600L
                        unit.startsWith("min") -> 60L
                        else -> 1L
                    }
                    val seconds = amount * multiplier
                    if (amount <= 0 || seconds !in 1..86400) {
                        deviceStatus.text = "Choose a PC timer between 1 second and 24 hours."
                        return
                    }
                    goal = "Start a Windows timer for $query"
                    steps.put(
                        JSONObject()
                            .put("step_id", "start-pc-timer")
                            .put("capability", "device.timer.create")
                            .put("target_platform", "desktop")
                            .put("title", "Start a timer on the Windows PC")
                            .put("arguments", JSONObject().put("seconds", seconds))
                    )
                }
                openPageMatch != null -> {
                    val rawAddress = openPageMatch.groupValues[1].trim().trimEnd('.', ',', ')')
                    val address = if (rawAddress.startsWith("https://", true)) rawAddress else "https://$rawAddress"
                    val parsed = try { java.net.URI(address) } catch (_: Exception) { null }
                    if (address.length > 2048 || parsed?.scheme != "https" || parsed.host.isNullOrBlank() || parsed.userInfo != null) {
                        deviceStatus.text = "Use a valid HTTPS website address, such as https://google.com."
                        return
                    }
                    goal = "Open $address in Chrome"
                    steps.put(JSONObject().put("step_id", "open-browser-tab").put("capability", "browser.open_tab")
                        .put("target_platform", "browser").put("title", "Open the requested website in Chrome")
                        .put("arguments", JSONObject().put("url", address)))
                }
                readPageMatch != null -> {
                    goal = "Read the currently active Chrome page"
                    steps.put(JSONObject().put("step_id", "read-active-browser-page").put("capability", "browser.read_visible_page")
                        .put("target_platform", "browser").put("title", "Read visible text from the active, user-authorized Chrome page")
                        .put("arguments", JSONObject()))
                }
                searchMatch != null -> {
                    val productQuery = searchMatch.groupValues[1].trim().take(200)
                    if (productQuery.isBlank()) {
                        deviceStatus.text = "Tell VOSI what product to search for."
                        return
                    }
                    goal = "Search Flipkart for $productQuery"
                    steps.put(
                        JSONObject()
                            .put("step_id", "search-flipkart-products")
                            .put("capability", "browser.search_products")
                            .put("target_platform", "browser")
                            .put("title", "Search Flipkart product listings")
                            .put("arguments", JSONObject().put("query", productQuery))
                    )
                }
                else -> {
                    deviceStatus.text = "Try: alarm for 5 PM on my PC/phone, set phone volume to 70%, mute PC, timer for 20 minutes, open https://google.com in Chrome, read this page, or search body spray on Flipkart."
                    return
                }
            }
        }

        sendDeviceCommandButton.isEnabled = false
        deviceStatus.text = "Sending your command to VOSI…"
        thread {
            try {
                val baseUrl = credential.getString("backend_url")
                val token = credential.getString("device_token")
                val payload = JSONObject()
                    .put("goal", goal)
                    .put("steps", steps)
                    .put("idempotency_key", java.util.UUID.randomUUID().toString())
                val (code, body) = requestDeviceApi(
                    baseUrl,
                    "/agent/tasks/request",
                    "POST",
                    token = token,
                    body = payload
                )
                val response = JSONObject(body)
                if (code !in 200..299 || !response.optBoolean("success")) {
                    throw IllegalStateException(response.optString("detail", "VOSI could not accept this command."))
                }
                val task = response.getJSONObject("task")
                runOnUiThread {
                    deviceCommandInput.text.clear()
                    deviceStatus.text = "Command queued for VOSI • Task " + task.optString("task_id").take(8) + ". Waiting for the target device to execute and confirm it."
                    sendDeviceCommandButton.isEnabled = true
                }
            } catch (error: Exception) {
                runOnUiThread {
                    deviceStatus.text = "Could not send command: " + (error.message ?: "backend unavailable")
                    sendDeviceCommandButton.isEnabled = true
                }
            }
        }
    }

    private fun heartbeatPhoneDevice() {
        val credential = DeviceCredentialStore.load(this)
        if (credential == null) {
            deviceStatus.text = "Pair this phone with VOSI first."
            return
        }
        heartbeatDeviceButton.isEnabled = false
        thread {
            try {
                val baseUrl = credential.getString("backend_url")
                val deviceId = credential.getString("device_id")
                val token = credential.getString("device_token")
                val (code, body) = requestDeviceApi(
                    baseUrl,
                    "/agent/devices/${Uri.encode(deviceId)}/heartbeat",
                    "POST",
                    token = token
                )
                val response = JSONObject(body)
                if (code in 200..299 && response.optBoolean("success")) {
                    pollPhoneAgentTasks(baseUrl, token)
                    refreshOriginTaskUpdates(baseUrl, token)
                }
                runOnUiThread {
                    if (code in 200..299 && response.optBoolean("success")) {
                        deviceStatus.text = "VOSI connected • phone task executor active."
                    } else {
                        deviceStatus.text = response.optString("detail", "VOSI connection failed (HTTP $code).")
                    }
                    heartbeatDeviceButton.isEnabled = true
                }
            } catch (error: Exception) {
                runOnUiThread {
                    deviceStatus.text = "VOSI is unreachable: ${error.message ?: "check backend URL and USB forwarding"}"
                    heartbeatDeviceButton.isEnabled = true
                }
            }
        }
    }

    private fun pollPhoneAgentTasks(baseUrl: String, token: String) {
        val (queueCode, queueBody) = requestDeviceApi(baseUrl, "/agent/tasks/available", "GET", token)
        if (queueCode !in 200..299) return
        val tasks = JSONObject(queueBody).optJSONArray("tasks") ?: JSONArray()
        for (index in 0 until minOf(tasks.length(), 3)) {
            val task = tasks.optJSONObject(index) ?: continue
            val capability = task.optString("capability")
            if (capability !in setOf("device.alarm.create", "device.volume.set")) continue
            val taskId = task.optString("task_id")
            val (claimCode, claimBody) = requestDeviceApi(
                baseUrl,
                "/agent/tasks/${Uri.encode(taskId)}/claim",
                "POST",
                token
            )
            if (claimCode !in 200..299) continue
            val step = JSONObject(claimBody).optJSONObject("step") ?: continue
            val stepId = step.optString("step_id")
            try {
                val args = step.optJSONObject("arguments") ?: JSONObject()
                val confirmation: String
                when (step.optString("capability")) {
                    "device.volume.set" -> {
                        val percent = args.optInt("volume", -1)
                        if (percent !in 0..100) throw IllegalArgumentException("Phone volume must be between 0 and 100.")
                        val audio = getSystemService(Context.AUDIO_SERVICE) as AudioManager
                        val maxVolume = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                        val target = (maxVolume * percent / 100.0).toInt()
                        audio.setStreamVolume(AudioManager.STREAM_MUSIC, target, 0)
                        val actual = audio.getStreamVolume(AudioManager.STREAM_MUSIC)
                        if (actual != target) throw IllegalStateException("Android did not apply the requested volume.")
                        confirmation = "Phone media volume set to $percent%."
                    }
                    "device.alarm.create" -> {
                        val hour = args.optInt("hour", -1)
                        val minute = args.optInt("minute", 0)
                        if (hour !in 0..23 || minute !in 0..59) throw IllegalArgumentException("Use a valid 24-hour alarm time.")
                        val alarmTime = Calendar.getInstance().apply {
                            set(Calendar.HOUR_OF_DAY, hour)
                            set(Calendar.MINUTE, minute)
                            set(Calendar.SECOND, 0)
                            set(Calendar.MILLISECOND, 0)
                            if (timeInMillis <= System.currentTimeMillis()) add(Calendar.DAY_OF_YEAR, 1)
                        }
                        val alarmIntent = Intent(this, VosiAlarmReceiver::class.java)
                            .putExtra("title", "VOSI alarm")
                        val pending = PendingIntent.getBroadcast(
                            this,
                            taskId.hashCode(),
                            alarmIntent,
                            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                        )
                        val manager = getSystemService(Context.ALARM_SERVICE) as AlarmManager
                        manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, alarmTime.timeInMillis, pending)
                        confirmation = "Phone alarm scheduled for ${String.format("%02d:%02d", hour, minute)}."
                    }
                    else -> throw IllegalArgumentException("Unsupported Android task capability.")
                }
                val result = JSONObject()
                    .put("success", true)
                    .put("verified", true)
                    .put("receipt", JSONObject()
                        .put("capability", step.optString("capability"))
                        .put("confirmation", confirmation))
                val (resultCode, _) = requestDeviceApi(
                    baseUrl,
                    "/agent/tasks/${Uri.encode(taskId)}/steps/${Uri.encode(stepId)}/result",
                    "POST",
                    token,
                    result
                )
                if (resultCode !in 200..299) throw IllegalStateException("VOSI could not save the Android execution receipt (HTTP $resultCode).")
            } catch (error: Exception) {
                val failed = JSONObject()
                    .put("success", false)
                    .put("verified", false)
                    .put("receipt", JSONObject())
                    .put("error", (error.message ?: "Android task failed").take(1500))
                requestDeviceApi(
                    baseUrl,
                    "/agent/tasks/${Uri.encode(taskId)}/steps/${Uri.encode(stepId)}/result",
                    "POST",
                    token,
                    failed
                )
            }
        }
    }

    private fun browserRecommendationSpeech(task: JSONObject): String? {
        val steps = task.optJSONArray("steps") ?: return null
        val products = mutableListOf<JSONObject>()
        for (index in 0 until steps.length()) {
            val step = steps.optJSONObject(index) ?: continue
            if (step.optString("capability") != "browser.search_products") continue
            val receipt = step.optJSONObject("receipt") ?: continue
            val items = receipt.optJSONArray("products") ?: continue
            for (productIndex in 0 until items.length()) {
                items.optJSONObject(productIndex)?.let { products.add(it) }
            }
        }
        if (products.isEmpty()) return null

        fun rating(product: JSONObject): Double =
            product.optString("rating").toDoubleOrNull() ?: 0.0
        fun reviews(product: JSONObject): Long =
            product.optString("reviews").filter { it.isDigit() }.toLongOrNull() ?: 0L
        fun price(product: JSONObject): Long =
            Regex("[0-9,]+").find(product.optString("price"))?.value
                ?.replace(",", "")?.toLongOrNull() ?: Long.MAX_VALUE

        val ranked = products.distinctBy { it.optString("url").ifBlank { it.optString("name") } }
            .sortedWith(
                compareByDescending<JSONObject> { rating(it) }
                    .thenByDescending { reviews(it) }
                    .thenBy { price(it) }
            )
            .take(3)
        val lines = ranked.mapIndexed { index, product ->
            val name = product.optString("name", "Product").replace(Regex("\\s+"), " ").take(90)
            val shownPrice = product.optString("price").ifBlank { "price not shown" }
            val shownRating = product.optString("rating").takeIf { it.isNotBlank() }
            val ratingText = shownRating?.let { ", rated $it out of 5" } ?: ""
            "${index + 1}. $name, $shownPrice$ratingText"
        }
        return "VOSI found ${products.size} visible products on Flipkart. " +
            "These options are ranked using the ratings, review counts, and prices visible on the page. " +
            lines.joinToString(". ", postfix = ".")
    }

    private fun speakBrowserRecommendation(message: String) {
        if (!activityResumed || !textToSpeechReady ||
            !getSharedPreferences("vosi_companion_settings", MODE_PRIVATE)
                .getBoolean("spoken_browser_results", false)
        ) return
        textToSpeech?.speak(message, TextToSpeech.QUEUE_FLUSH, null, "vosi-browser-${System.currentTimeMillis()}")
    }

    private fun refreshOriginTaskUpdates(baseUrl: String, token: String) {
        val (code, body) = requestDeviceApi(baseUrl, "/agent/tasks/updates", "GET", token)
        if (code !in 200..299) return
        val updates = JSONObject(body).optJSONArray("updates") ?: JSONArray()
        val preferences = getSharedPreferences("vosi_task_notifications", MODE_PRIVATE)
        for (index in 0 until updates.length()) {
            val task = updates.optJSONObject(index) ?: continue
            val state = task.optString("state")
            if (state !in setOf("completed", "failed", "cancelled")) continue
            val taskId = task.optString("task_id")
            if (preferences.getString(taskId, null) == state) continue
            val goal = task.optString("goal", "VOSI task")
            val stepArray = task.optJSONArray("steps") ?: JSONArray()
            var detail = if (state == "completed") "Task completed successfully." else "Task $state."
            for (stepIndex in 0 until stepArray.length()) {
                val step = stepArray.optJSONObject(stepIndex) ?: continue
                val receipt = step.optJSONObject("receipt")
                if (receipt != null && receipt.has("confirmation")) detail = receipt.optString("confirmation")
                if (step.optString("error").isNotBlank()) detail = step.optString("error")
            }
            notifyVosiTaskUpdate(taskId, goal, detail, state)
            val spokenRecommendation = if (state == "completed") browserRecommendationSpeech(task) else null
            if (!spokenRecommendation.isNullOrBlank()) {
                runOnUiThread { speakBrowserRecommendation(spokenRecommendation) }
            }
            preferences.edit().putString(taskId, state).apply()
        }
    }

    private fun notifyVosiTaskUpdate(taskId: String, title: String, detail: String, state: String) {
        val channelId = "vosi_task_updates"
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(channelId, "VOSI task updates", NotificationManager.IMPORTANCE_DEFAULT)
            )
        }
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, channelId)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        val notification = builder
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(if (state == "completed") "VOSI task completed" else "VOSI task $state")
            .setContentText("$title • $detail")
            .setStyle(Notification.BigTextStyle().bigText("$title\n$detail"))
            .setAutoCancel(true)
            .build()
        try {
            manager.notify(taskId.hashCode(), notification)
        } catch (_: SecurityException) {
            runOnUiThread { deviceStatus.text = "VOSI task $state: $title — $detail" }
        }
    }

    override fun onDestroy() {
        textToSpeech?.stop()
        textToSpeech?.shutdown()
        textToSpeech = null
        textToSpeechReady = false
        super.onDestroy()
    }

    private fun disconnectPhoneDevice() {
        val credential = DeviceCredentialStore.load(this)
        if (credential == null) {
            deviceStatus.text = "This phone is not paired."
            return
        }
        disconnectDeviceButton.isEnabled = false
        thread {
            try {
                val (code, body) = requestDeviceApi(
                    credential.getString("backend_url"),
                    "/agent/devices/me",
                    "DELETE",
                    token = credential.getString("device_token")
                )
                val response = JSONObject(body)
                if (code !in 200..299 || !response.optBoolean("revoked")) {
                    throw IllegalStateException(response.optString("detail", "Server did not revoke this device."))
                }
                DeviceCredentialStore.clear(this)
                runOnUiThread {
                    deviceStatus.text = "Phone disconnected and its VOSI credential revoked."
                    refreshPairedDeviceStatus()
                    disconnectDeviceButton.isEnabled = true
                }
            } catch (error: Exception) {
                runOnUiThread {
                    deviceStatus.text = "Could not revoke phone: ${error.message ?: "backend unavailable"}"
                    disconnectDeviceButton.isEnabled = true
                }
            }
        }
    }

    private fun matchWidth(): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)

    private fun openNotificationAccessSettings() {
        try {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        } catch (_: Exception) {
            status.text = "Open Android Settings > Notifications > Device & app notifications, then enable VOSI Companion."
        }
    }

    private fun refreshWhatsAppMessages() {
        if (!::messagesContainer.isInitialized) return
        messagesContainer.removeAllViews()
        val enabled = WhatsAppNotificationListener.isNotificationAccessEnabled(this)
        messagesContainer.addView(TextView(this).apply {
            text = if (enabled) "Notification access: ENABLED" else "Notification access: NOT ENABLED"
            textSize = 14f
            setPadding(0, 8, 0, 8)
        })

        val messages = WhatsAppNotificationListener.recentMessages(this)
        if (messages.isEmpty()) {
            messagesContainer.addView(TextView(this).apply {
                text = "No WhatsApp notification previews yet. Enable access, then receive a new WhatsApp message with notification previews turned on."
                textSize = 13f
                setPadding(0, 4, 0, 12)
            })
            return
        }

        messages.take(20).forEach { item ->
            val key = item.optString("key")
            val sender = item.optString("sender", "WhatsApp")
            val message = item.optString("message")
            messagesContainer.addView(TextView(this).apply {
                text = "$sender\n$message"
                textSize = 14f
                setPadding(0, 10, 0, 4)
            })
            messagesContainer.addView(Button(this).apply {
                text = "Reply to $sender"
                setOnClickListener { promptNotificationReply(key, sender) }
            }, matchWidth())
        }
    }

    private fun syncWhatsAppWithDesktop() {
        val token = companionToken.text.toString().trim()
        if (token.isBlank()) {
            status.text = "Enter your private desktop pairing token first."
            return
        }
        if (!WhatsAppNotificationListener.isNotificationAccessEnabled(this)) {
            status.text = "Enable WhatsApp notification access before syncing."
            return
        }

        getSharedPreferences("vosi_companion_settings", MODE_PRIVATE)
            .edit()
            .putString("pairing_token", token)
            .apply()

        syncButton.isEnabled = false
        status.text = "Connecting to desktop VOSI..."

        thread {
            var connection: HttpURLConnection? = null
            try {
                val recent = WhatsAppNotificationListener.recentMessages(this).take(30)
                val messageArray = JSONArray().apply {
                    recent.forEach { put(it) }
                }
                val payload = JSONObject().put("messages", messageArray)

                connection = (URL(
                    "http://127.0.0.1:8001/companion/whatsapp/sync"
                ).openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = 10000
                    readTimeout = 15000
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    setRequestProperty("Authorization", "Bearer $token")
                }

                connection.outputStream.use { output ->
                    output.write(payload.toString().toByteArray(Charsets.UTF_8))
                }

                val responseCode = connection.responseCode
                val responseText = if (responseCode in 200..299) {
                    connection.inputStream.bufferedReader().use { it.readText() }
                } else {
                    connection.errorStream?.bufferedReader()?.use { it.readText() }
                        ?: "HTTP $responseCode"
                }

                runOnUiThread {
                    if (responseCode in 200..299) {
                        val result = JSONObject(responseText)
                        status.text =
                            "Sync successful! ${result.optInt("received")} WhatsApp previews sent to desktop VOSI."
                    } else if (responseCode == 401) {
                        status.text = "Sync rejected. Check the desktop pairing token."
                    } else {
                        status.text = "Sync failed (HTTP $responseCode). Check that the VOSI backend is running."
                    }
                    syncButton.isEnabled = true
                }
            } catch (error: Exception) {
                runOnUiThread {
                    status.text =
                        "Could not connect to desktop VOSI. Check USB connection and ADB forwarding. ${error.message ?: ""}"
                    syncButton.isEnabled = true
                }
            } finally {
                connection?.disconnect()
            }
        }
    }

    private fun promptNotificationReply(key: String, sender: String) {
        val input = EditText(this).apply {
            hint = "Write your WhatsApp reply"
            minLines = 2
        }
        AlertDialog.Builder(this)
            .setTitle("Reply to $sender")
            .setView(input)
            .setNegativeButton("Cancel", null)
            .setPositiveButton("Send reply") { _, _ ->
                val reply = input.text.toString().trim()
                if (reply.isBlank()) {
                    status.text = "Type a reply first."
                } else {
                    val sent = WhatsAppNotificationListener.replyToNotification(key, reply)
                    status.text = if (sent) {
                        "Reply action sent to WhatsApp."
                    } else {
                        "This notification no longer has an active quick-reply action. Open the WhatsApp chat to reply instead."
                    }
                }
            }
            .show()
    }

    private fun openWhatsAppChat() {
        val number = phoneNumber.text.toString().filter { it.isDigit() }
        if (number.isBlank()) {
            status.text = "Enter a phone number including its country code first."
            return
        }
        val message = whatsappMessage.text.toString()
        val url = "https://wa.me/$number?text=${Uri.encode(message)}"
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
            status.text = "WhatsApp chat opened. Review the recipient and tap Send in WhatsApp."
        } catch (error: Exception) {
            status.text = "Could not open WhatsApp: ${error.message ?: "unknown error"}"
        }
    }

    private fun findContact() {
        if (checkSelfPermission(Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.READ_CONTACTS), contactsPermission)
            return
        }

        val query = contactName.text.toString().trim()
        if (query.isEmpty()) {
            status.text = "Enter a contact name first."
            return
        }

        val projection = arrayOf(
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
            ContactsContract.CommonDataKinds.Phone.NUMBER
        )
        val selection = "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} LIKE ?"
        val args = arrayOf("%$query%")

        try {
            contentResolver.query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                projection,
                selection,
                args,
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " ASC"
            )?.use { cursor ->
                if (!cursor.moveToFirst()) {
                    status.text = "No matching contact found. Check the name and try again."
                    return
                }
                val name = cursor.getString(0) ?: query
                val number = cursor.getString(1) ?: ""
                phoneNumber.setText(number)
                status.text = "Found $name. Check the number before calling or opening WhatsApp."
            }
        } catch (_: SecurityException) {
            status.text = "Contacts permission was not granted."
        }
    }

    private fun confirmAndCall() {
        val number = phoneNumber.text.toString().trim()
        if (number.isEmpty()) {
            status.text = "Find a contact or enter a phone number first."
            return
        }
        AlertDialog.Builder(this)
            .setTitle("Confirm phone call")
            .setMessage("VOSI is about to call $number. Continue?")
            .setNegativeButton("Cancel", null)
            .setPositiveButton("Call") { _, _ -> placeCall(number) }
            .show()
    }

    private fun placeCall(number: String) {
        if (checkSelfPermission(Manifest.permission.CALL_PHONE) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.CALL_PHONE), callPermission)
            return
        }
        try {
            startActivity(Intent(Intent.ACTION_CALL, Uri.parse("tel:${Uri.encode(number)}")))
        } catch (error: Exception) {
            status.text = "Unable to start the call: ${error.message ?: "unknown error"}"
        }
    }

    @Deprecated("Uses Android's permission callback for broad device compatibility")
    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
        when (requestCode) {
            contactsPermission -> status.text =
                if (granted) "Contacts permission granted. Tap Find contact again."
                else "Contacts permission denied. You can still enter a number manually."
            callPermission -> status.text =
                if (granted) "Call permission granted. Tap Call this number again to confirm."
                else "Call permission denied. Calling is disabled until you grant it."
            voicePermission -> if (granted) startVoiceConversation() else deviceStatus.text =
                "Microphone permission denied. Tap Talk to VOSI after allowing microphone access."
            102 -> deviceStatus.text =
                if (granted) "VOSI task and alarm notifications enabled."
                else "Notifications are disabled. VOSI can still execute tasks, but Android may hide completion alerts."
        }
    }
}
