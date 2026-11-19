package com.vosi.companion

import android.telecom.Call
import android.telecom.CallScreeningService

/**
 * Native Android call screening only. This service does not answer calls or access call audio.
 * If busy mode and unknown-caller screening are both enabled, unknown callers are silenced
 * (not rejected) so the caller can still leave a voicemail.
 */
class VosiCallScreeningService : CallScreeningService() {
    override fun onScreenCall(callDetails: Call.Details) {
        val incoming = callDetails.callDirection == Call.Details.DIRECTION_INCOMING
        val prefs = getSharedPreferences("vosi_call_assistant", MODE_PRIVATE)
        val busyMode = prefs.getBoolean("busy_mode", false)
        val screenUnknown = prefs.getBoolean("unknown_callers", false)
        val contactName = callDetails.contactDisplayName?.trim().orEmpty()
        val isKnownContact = contactName.isNotEmpty()

        val silence = incoming && busyMode && screenUnknown && !isKnownContact
        val response = CallResponse.Builder()
            .setDisallowCall(false)
            .setRejectCall(false)
            .setSkipCallLog(false)
            .setSkipNotification(false)
            .setSilenceCall(silence)
            .build()

        respondToCall(callDetails, response)
    }
}