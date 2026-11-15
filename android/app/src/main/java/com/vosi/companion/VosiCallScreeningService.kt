package com.vosi.companion

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.telecom.Call
import android.telecom.CallScreeningService
import java.text.DateFormat
import java.util.Date

/**
 * Receives incoming-call metadata only after the user explicitly grants Android's
 * call-screening role. This service never answers, rejects, records, or injects audio.
 */
class VosiCallScreeningService : CallScreeningService() {
    override fun onScreenCall(details: Call.Details) {
        val number = details.handle?.schemeSpecificPart.orEmpty().take(80)
        val incoming = details.callDirection == Call.Details.DIRECTION_INCOMING
        if (incoming) {
            val prefs = getSharedPreferences("vosi_call_screening", Context.MODE_PRIVATE)
            prefs.edit()
                .putString("last_incoming_number", number)
                .putLong("last_incoming_at", System.currentTimeMillis())
                .apply()
            postIncomingCallNotice(number)
        }

        // Preserve normal Android call behavior. No call is answered or blocked.
        val response = CallResponse.Builder()
            .setDisallowCall(false)
            .setRejectCall(false)
            .setSkipCallLog(false)
            .setSkipNotification(false)
            .build()
        respondToCall(details, response)
    }

    private fun postIncomingCallNotice(number: String) {
        val channelId = "vosi_incoming_calls"
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(channelId, "VOSI incoming call alerts", NotificationManager.IMPORTANCE_DEFAULT)
            )
        }
        val openSetup = Intent(this, IncomingCallSetupActivity::class.java)
        val pending = PendingIntent.getActivity(
            this, 7102, openSetup,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val caller = number.ifBlank { "Private or unavailable number" }
        @Suppress("DEPRECATION")
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, channelId)
        } else {
            Notification.Builder(this)
        }
        val notification = builder
            .setSmallIcon(android.R.drawable.sym_action_call)
            .setContentTitle("Incoming call detected by VOSI")
            .setContentText(caller)
            .setStyle(Notification.BigTextStyle().bigText("Caller: $caller\nVOSI has detected this call. Android still controls answering."))
            .setContentIntent(pending)
            .setAutoCancel(true)
            .build()
        try {
            manager.notify(7102, notification)
        } catch (_: SecurityException) {
            // Call screening must never fail because notifications are disabled.
        }
    }
}
