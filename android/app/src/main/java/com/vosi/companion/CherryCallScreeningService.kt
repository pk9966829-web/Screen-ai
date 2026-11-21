package com.vosi.companion

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.net.Uri
import android.os.Build
import android.telecom.Call
import android.telecom.CallScreeningService
import androidx.core.app.NotificationCompat

/**
 * Opt-in call screening foundation. This service never rejects or answers calls.
 * Full AI conversations require a separate, supported PSTN/call-forwarding audio route.
 */
class CherryCallScreeningService : CallScreeningService() {
    override fun onScreenCall(details: Call.Details) {
        val response = CallResponse.Builder()
            .setDisallowCall(false)
            .setRejectCall(false)
            .setSilenceCall(false)
            .setSkipCallLog(false)
            .setSkipNotification(false)
            .build()

        respondToCall(details, response)

        val prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!prefs.getBoolean(KEY_SCREENING_ENABLED, false)) return
        if (details.callDirection != Call.Details.DIRECTION_INCOMING) return

        val number = details.handle?.schemeSpecificPart?.takeIf { it.isNotBlank() } ?: "Unknown number"
        showIncomingCallNotice(number)
    }

    private fun showIncomingCallNotice(number: String) {
        val manager = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Call assistant", NotificationManager.IMPORTANCE_DEFAULT)
            )
        }
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.sym_call_incoming)
            .setContentTitle("CHERRY AI noticed an incoming call")
            .setContentText(number)
            .setStyle(NotificationCompat.BigTextStyle().bigText("Incoming call from $number. This is call detection only; CHERRY AI has not answered the call."))
            .setAutoCancel(true)
            .build()
        manager.notify(number.hashCode(), notification)
    }

    companion object {
        const val PREFS = "cherry_call_assistant"
        const val KEY_SCREENING_ENABLED = "screening_enabled"
        private const val CHANNEL_ID = "cherry_call_assistant"
    }
}
