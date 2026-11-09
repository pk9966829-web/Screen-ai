package com.vosi.companion

import android.app.Notification
import android.app.PendingIntent
import android.app.RemoteInput
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import org.json.JSONArray
import org.json.JSONObject

/**
 * Reads only notifications posted by the user's installed WhatsApp app.
 * Notification contents stay on this Android device in private app storage.
 */
class WhatsAppNotificationListener : NotificationListenerService() {
    override fun onListenerConnected() {
        super.onListenerConnected()
        activeInstance = this
    }

    override fun onListenerDisconnected() {
        if (activeInstance === this) activeInstance = null
        super.onListenerDisconnected()
    }

    override fun onDestroy() {
        if (activeInstance === this) activeInstance = null
        super.onDestroy()
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (sbn.packageName != WHATSAPP_PACKAGE) return
        val notification = sbn.notification ?: return
        if ((notification.flags and Notification.FLAG_GROUP_SUMMARY) != 0) return

        val extras = notification.extras ?: return
        val sender = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString()?.trim().orEmpty()
        val message = (
            extras.getCharSequence(Notification.EXTRA_BIG_TEXT)
                ?: extras.getCharSequence(Notification.EXTRA_TEXT)
            )?.toString()?.trim().orEmpty()
        if (message.isBlank()) return

        val item = JSONObject().apply {
            put("key", sbn.key)
            put("sender", sender.ifBlank { "WhatsApp message" })
            put("message", message)
            put("postedAt", sbn.postTime)
        }
        saveMessage(applicationContext, item)
    }

    // Replies only when this active WhatsApp notification exposes a RemoteInput action.
    private fun replyToActiveNotification(key: String, text: String): Boolean {
        if (text.isBlank()) return false
        val sbn = activeNotifications?.firstOrNull { it.key == key } ?: return false
        if (sbn.packageName != WHATSAPP_PACKAGE) return false

        val actions = sbn.notification.actions ?: return false
        val replyAction = actions.firstOrNull { !it.remoteInputs.isNullOrEmpty() } ?: return false
        val remoteInputs = replyAction.remoteInputs ?: return false
        val fillInIntent = Intent()
        val results = Bundle().apply {
            remoteInputs.forEach { putCharSequence(it.resultKey, text) }
        }

        return try {
            RemoteInput.addResultsToIntent(remoteInputs, fillInIntent, results)
            replyAction.actionIntent.send(this, 0, fillInIntent)
            true
        } catch (_: PendingIntent.CanceledException) {
            false
        } catch (_: SecurityException) {
            false
        }
    }

    companion object {
        const val WHATSAPP_PACKAGE = "com.whatsapp"
        private const val PREFS = "vosi_whatsapp_local"
        private const val KEY_MESSAGES = "recent_messages"
        private var activeInstance: WhatsAppNotificationListener? = null

        fun isNotificationAccessEnabled(context: Context): Boolean {
            val expected = ComponentName(context, WhatsAppNotificationListener::class.java)
            val enabled = android.provider.Settings.Secure.getString(
                context.contentResolver, "enabled_notification_listeners"
            ) ?: return false
            return enabled.split(":").any { ComponentName.unflattenFromString(it) == expected }
        }

        fun recentMessages(context: Context): List<JSONObject> {
            val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_MESSAGES, "[]") ?: "[]"
            return try {
                val array = JSONArray(raw)
                (0 until array.length()).mapNotNull { array.optJSONObject(it) }
                    .sortedByDescending { it.optLong("postedAt") }
            } catch (_: Exception) {
                emptyList()
            }
        }

        fun replyToNotification(key: String, text: String): Boolean =
            activeInstance?.replyToActiveNotification(key, text) == true

        private fun saveMessage(context: Context, item: JSONObject) {
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val old = try {
                JSONArray(prefs.getString(KEY_MESSAGES, "[]") ?: "[]")
            } catch (_: Exception) {
                JSONArray()
            }
            val updated = JSONArray()
            updated.put(item)
            for (index in 0 until old.length()) {
                val previous = old.optJSONObject(index) ?: continue
                if (previous.optString("key") == item.optString("key")) continue
                if (updated.length() >= 30) break
                updated.put(previous)
            }
            prefs.edit().putString(KEY_MESSAGES, updated.toString()).apply()
        }

        fun clearMessages(context: Context) {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().remove(KEY_MESSAGES).apply()
        }
    }
}
