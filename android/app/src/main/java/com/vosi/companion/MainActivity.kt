package com.vosi.companion

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.ContactsContract
import android.provider.Settings
import android.text.InputType
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
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
    private val contactsPermission = 100
    private val callPermission = 101

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
        refreshPairedDeviceStatus()
    }

    override fun onResume() {
        super.onResume()
        refreshWhatsAppMessages()
        if (::deviceStatus.isInitialized) {
            refreshPairedDeviceStatus()
            if (DeviceCredentialStore.load(this) != null) heartbeatPhoneDevice()
        }
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
        body: JSONObject? = null
    ): Pair<Int, String> {
        val connection = (URL(baseUrl + path).openConnection() as HttpURLConnection)
        try {
            connection.requestMethod = method
            connection.connectTimeout = 10000
            connection.readTimeout = 15000
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
                }
            } catch (error: Exception) {
                runOnUiThread {
                    deviceStatus.text = "Could not pair phone: ${error.message ?: "backend unavailable"}"
                    pairDeviceButton.isEnabled = true
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
        val goal: String
        val alarmMatch = Regex(
            """(?:set|create)\s+(?:an?\s+)?alarm\s+(?:for\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?:\s+(?:on|in)\s+(?:my\s+)?pc)?""",
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
            goal = "Set a Windows alarm for $query"
            steps.put(
                JSONObject()
                    .put("step_id", "set-desktop-alarm")
                    .put("capability", "device.alarm.create")
                    .put("target_platform", "desktop")
                    .put("title", "Set an alarm on the paired Windows PC")
                    .put("arguments", JSONObject().put("hour", hour).put("minute", minute))
            )
        } else {
            val searchMatch = Regex(
                """^(?:search|find)\s+(.+?)\s+on\s+flipkart\s*$""",
                RegexOption.IGNORE_CASE
            ).find(query)
            if (searchMatch == null) {
                deviceStatus.text = "For now, try: “set an alarm for 5 PM on my PC” or “search body spray under 1000 on Flipkart”."
                return
            }
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
                    deviceStatus.text = "Command queued for VOSI • Task " + task.optString("task_id").take(8) + ". The paired PC or Chrome browser will execute it and report its receipt."
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
                runOnUiThread {
                    deviceStatus.text = if (code in 200..299 && response.optBoolean("success")) {
                        "VOSI connected • heartbeat confirmed."
                    } else {
                        response.optString("detail", "VOSI connection failed (HTTP $code).")
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
        }
    }
}
