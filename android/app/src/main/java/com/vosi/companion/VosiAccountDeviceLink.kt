package com.vosi.companion

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Links the locally paired device to the signed-in VOSI account.
 * Device credentials and account sessions remain separate and are never sent in the same header.
 */
object VosiAccountDeviceLink {
    fun linkIfSignedIn(credential: JSONObject): String? {
        val accountToken = AccountSessionStore.load() ?: return null
        return try {
            val backend = credential.optString("backend_url").trimEnd('/')
            val deviceId = credential.optString("device_id")
            val deviceToken = credential.optString("device_token")
            require(backend.startsWith("https://") || backend.startsWith("http://")) {
                "The paired VOSI backend URL is invalid."
            }
            require(deviceId.isNotBlank() && deviceToken.isNotBlank()) {
                "The paired device credential is incomplete. Pair this phone again."
            }
            val encodedId = URLEncoder.encode(deviceId, Charsets.UTF_8.name())
            val connection = URL("$backend/identity/devices/link?device_id=$encodedId")
                .openConnection() as HttpURLConnection
            try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 10000
            connection.readTimeout = 15000
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("Authorization", "Bearer $accountToken")
            connection.setRequestProperty("X-Vosi-Device-Token", deviceToken)
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val raw = stream?.bufferedReader()?.use { it.readText() } ?: "{}"
            val response = JSONObject(raw)
            if (code !in 200..299 || !response.optBoolean("success")) {
                return response.optString("detail", "Could not link this phone to your VOSI account (HTTP $code).")
            }
            null
            } finally {
                connection.disconnect()
            }
        } catch (error: Exception) {
            error.message ?: "Could not link this phone to your VOSI account."
        }
    }
}
